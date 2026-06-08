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
# Fabryka
# --------------------------------------------------------------------------- #
def build_backend(name: str, **kwargs) -> TTSBackend:
    """Tworzy backend po nazwie. Nieznane kwargs sa ignorowane przez backend."""
    name = name.lower()
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
    raise TTSError(f"Nieznany backend TTS: {name}. Dostepne: piper, elevenlabs")
