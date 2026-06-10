"""Backendy syntezy mowy (TTS) — wymienne silniki.

Wspolny interfejs: TTSBackend.synthesize(text, out_path) zapisuje jeden plik
audio dla fragmentu tekstu. Reszta potoku nie wie, ktory silnik jest uzyty.

Dostepne backendy:
    piper       — lokalny, darmowy, offline; gotowe polskie glosy (zalecany domyslnie)
    elevenlabs  — chmura; najlepsza jakosc i klonowanie glosu (wymaga klucza API)

Uwaga prawna dot. klonowania glosu realnej osoby (np. konkretnego lektora):
glos jest dobrem osobistym (art. 23 KC), a regulaminy uslug zwykle wymagaja
zgody osoby. Domyslnie celuj w glos *o pozadanych cechach* (gleboki baryton,
spokojna intonacja lektorska), a nie w wierna kopie konkretnej osoby.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class TTSError(RuntimeError):
    """Blad backendu syntezy mowy."""


class TTSBackend(ABC):
    """Wspolny interfejs dla silnikow TTS."""

    #: rozszerzenie pliku produkowanego przez backend (bez kropki)
    audio_ext: str = "wav"

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> None:
        """Syntetyzuje `text` i zapisuje do `out_path`."""

    def preflight(self) -> None:
        """Opcjonalna walidacja konfiguracji przed startem (klucze, modele)."""


# --------------------------------------------------------------------------- #
# espeak-ng — lokalny, offline, zero konfiguracji (jakosc "robotyczna")
# --------------------------------------------------------------------------- #
class EspeakBackend(TTSBackend):
    """Synteza przez `espeak-ng` — dziala od reki, bez pobierania modeli.

    Glos jest syntetyczny ("robotyczny"), ale backend nie wymaga GPU, kluczy
    ani plikow modeli — idealny do szybkiego testu calego potoku oraz jako
    fallback, gdy lepsze silniki sa niedostepne.
    """

    audio_ext = "wav"

    def __init__(
        self,
        *,
        voice: str = "pl",
        binary: str = "espeak-ng",
        speed: int = 160,
        pitch: int = 50,
    ) -> None:
        self.voice = voice
        self.binary = binary
        self.speed = speed
        self.pitch = pitch

    def preflight(self) -> None:
        if shutil.which(self.binary) is None:
            # Sprobuj tez klasycznego `espeak`.
            if shutil.which("espeak") is not None:
                self.binary = "espeak"
            else:
                raise TTSError(
                    f"Nie znaleziono '{self.binary}'. Zainstaluj espeak-ng "
                    "(apt-get install espeak-ng)."
                )

    def synthesize(self, text: str, out_path: Path) -> None:
        cmd = [
            self.binary, "-v", self.voice,
            "-s", str(self.speed), "-p", str(self.pitch),
            "-w", str(out_path), text,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out_path.exists():
            raise TTSError(f"espeak-ng nie powiodl sie:\n{proc.stderr[-1000:]}")


# --------------------------------------------------------------------------- #
# Piper — lokalny, offline
# --------------------------------------------------------------------------- #
class PiperBackend(TTSBackend):
    """Lokalna synteza przez binarke `piper`.

    Wymaga: zainstalowanego `piper` oraz modelu glosu (.onnx + .onnx.json).
    Polskie modele: https://huggingface.co/rhasspy/piper-voices (katalog pl/).
    Glebszy, "lektorski" charakter mozna podbic obnizajac tempo (length_scale > 1).
    """

    audio_ext = "wav"

    def __init__(
        self,
        model_path: str | Path,
        *,
        binary: str = "piper",
        length_scale: float = 1.05,
        noise_scale: float = 0.667,
        speaker: int | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.binary = binary
        self.length_scale = length_scale
        self.noise_scale = noise_scale
        self.speaker = speaker

    def preflight(self) -> None:
        if shutil.which(self.binary) is None:
            raise TTSError(
                f"Nie znaleziono binarki '{self.binary}'. "
                "Zainstaluj Piper: https://github.com/rhasspy/piper"
            )
        if not self.model_path.exists():
            raise TTSError(
                f"Brak modelu glosu: {self.model_path}. "
                "Pobierz polski glos z https://huggingface.co/rhasspy/piper-voices"
            )

    def synthesize(self, text: str, out_path: Path) -> None:
        cmd = [
            self.binary,
            "--model", str(self.model_path),
            "--output_file", str(out_path),
            "--length_scale", str(self.length_scale),
            "--noise_scale", str(self.noise_scale),
        ]
        if self.speaker is not None:
            cmd += ["--speaker", str(self.speaker)]

        proc = subprocess.run(
            cmd, input=text, text=True, capture_output=True
        )
        if proc.returncode != 0 or not out_path.exists():
            raise TTSError(f"Piper nie powiodl sie:\n{proc.stderr[-1500:]}")


# --------------------------------------------------------------------------- #
# ElevenLabs — chmura, najlepsza jakosc / klonowanie
# --------------------------------------------------------------------------- #
class ElevenLabsBackend(TTSBackend):
    """Synteza przez API ElevenLabs.

    Wymaga zmiennej srodowiskowej ELEVENLABS_API_KEY oraz voice_id.
    Aby uzyskac glos zblizony do danego lektora, mozna:
      - wybrac gotowy gleboki meski glos z biblioteki, lub
      - (za zgoda osoby!) stworzyc Professional Voice Clone z probek.
    """

    audio_ext = "mp3"
    _URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    def __init__(
        self,
        voice_id: str,
        *,
        model_id: str = "eleven_multilingual_v2",
        api_key: str | None = None,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
    ) -> None:
        self.voice_id = voice_id
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.style = style

    def preflight(self) -> None:
        if not self.api_key:
            raise TTSError(
                "Brak klucza API. Ustaw zmienna ELEVENLABS_API_KEY."
            )
        try:
            import requests  # noqa: F401
        except ImportError as exc:
            raise TTSError("Wymagane: pip install requests") from exc

    def synthesize(self, text: str, out_path: Path) -> None:
        import requests

        resp = requests.post(
            self._URL.format(voice_id=self.voice_id),
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": self.model_id,
                "voice_settings": {
                    "stability": self.stability,
                    "similarity_boost": self.similarity_boost,
                    "style": self.style,
                },
            },
            timeout=120,
        )
        if resp.status_code != 200:
            raise TTSError(
                f"ElevenLabs API {resp.status_code}: {resp.text[:500]}"
            )
        out_path.write_bytes(resp.content)


# --------------------------------------------------------------------------- #
# XTTS-v2 — lokalne klonowanie barwy z probki (Coqui)
# --------------------------------------------------------------------------- #
class XTTSBackend(TTSBackend):
    """Lokalna synteza z klonowaniem barwy przez XTTS-v2.

    Model zero-shot: barwe glosu przejmuje z pliku referencyjnego (`speaker_wav`)
    — kilka do kilkunastu sekund czystej mowy (najlepiej >6 s, bez muzyki/szumu).
    Obsluguje jezyk polski. Dziala na CPU, ale realnie wymaga GPU dla rozsadnego
    czasu syntezy.

    Wymaga: pip install coqui-tts  (oraz PyTorch). Model pobiera sie automatycznie
    przy pierwszym uruchomieniu.

    UWAGA PRAWNA: klonowanie barwy rozpoznawalnej, zyjacej osoby (np. konkretnego
    lektora) jest dopuszczalne tylko za jej zgoda lub do wlasnego, prywatnego
    uzytku — nie do dystrybucji. Glos jest dobrem osobistym (art. 23 KC).
    """

    audio_ext = "wav"
    DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(
        self,
        speaker_wav: str | Path,
        *,
        language: str = "pl",
        model_name: str | None = None,
        device: str | None = None,
        speed: float = 1.0,
        temperature: float = 0.65,
    ) -> None:
        self.speaker_wav = Path(speaker_wav)
        self.language = language
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        self.speed = speed
        self.temperature = temperature
        self._tts = None  # leniwie ladowany model (ciezki)

    def preflight(self) -> None:
        if not self.speaker_wav.exists():
            raise TTSError(
                f"Brak pliku referencyjnego barwy: {self.speaker_wav}. "
                "Podaj nagranie glosu (kilka-kilkanascie sekund czystej mowy)."
            )
        try:
            from TTS.api import TTS  # noqa: F401  (pakiet: coqui-tts)
        except ImportError as exc:
            missing = getattr(exc, "name", None)
            hint = ""
            if missing in {"torch", "torchaudio"}:
                hint = " Brakuje PyTorcha — zainstaluj: pip install torch torchaudio."
            elif missing in {"TTS", None}:
                hint = " Zainstaluj: pip install coqui-tts torch torchaudio."
            raise TTSError(
                f"Nie mozna zaladowac XTTS (brak modulu: {missing}).{hint} "
                f"Pelny blad importu: {exc}"
            ) from exc
        self._load()

    def _load(self) -> None:
        if self._tts is not None:
            return
        from TTS.api import TTS

        device = self.device
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        self._tts = TTS(self.model_name).to(device)

    def synthesize(self, text: str, out_path: Path) -> None:
        self._load()
        common = dict(
            text=text,
            speaker_wav=str(self.speaker_wav),
            language=self.language,
            file_path=str(out_path),
        )
        try:
            self._tts.tts_to_file(
                **common, speed=self.speed, temperature=self.temperature
            )
        except TypeError:
            # Starsze wersje API bez parametrow speed/temperature.
            self._tts.tts_to_file(**common)
        if not out_path.exists():
            raise TTSError("XTTS nie wygenerowal pliku audio.")


# --------------------------------------------------------------------------- #
# Fabryka
# --------------------------------------------------------------------------- #
def build_backend(name: str, **kwargs) -> TTSBackend:
    """Tworzy backend po nazwie. Nieznane kwargs sa ignorowane przez backend."""
    name = name.lower()
    if name == "espeak":
        return EspeakBackend(
            voice=kwargs.get("language", "pl"),
            speed=int(kwargs.get("speed_wpm", 160)),
        )
    if name == "piper":
        return PiperBackend(
            model_path=kwargs["voice"],
            length_scale=kwargs.get("length_scale", 1.05),
            speaker=kwargs.get("speaker"),
        )
    if name == "elevenlabs":
        return ElevenLabsBackend(
            voice_id=kwargs["voice"],
            model_id=kwargs.get("model_id", "eleven_multilingual_v2"),
        )
    if name == "xtts":
        return XTTSBackend(
            speaker_wav=kwargs["voice"],
            language=kwargs.get("language", "pl"),
            speed=kwargs.get("speed", 1.0),
            temperature=kwargs.get("temperature", 0.65),
            device=kwargs.get("device"),
        )
    raise TTSError(
        f"Nieznany backend TTS: {name}. Dostepne: espeak, piper, xtts, elevenlabs"
    )
