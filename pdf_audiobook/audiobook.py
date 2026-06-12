"""Orkiestracja: tekst -> fragmenty -> audio per fragment -> zlozony audiobook.

Laczenie audio:
  * jesli dostepny `ffmpeg` — uzywamy go (dowolny format, mozliwe rozdzialy),
  * w przeciwnym razie dla plikow WAV stosujemy czysto-pythonowy fallback (stdlib
    `wave`), wiec Piper dziala nawet bez ffmpeg.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from .chunk import chunk_text
from .clean import clean_text
from .extract import Book
from .normalize import normalize_text
from .tts import TTSBackend


@dataclass
class SynthOptions:
    max_chars: int = 600
    keep_chunks: bool = False
    normalize: bool = True
    pitch: float = 0.0   # przesuniecie wysokosci w poltonach (ujemne = nizej)
    resume: bool = False  # pomijaj fragmenty juz zsyntetyzowane (dlugie ksiazki)
    max_chunks: int | None = None  # syntetyzuj tylko pierwsze N fragmentow (probka)


@dataclass
class BookMeta:
    """Metadane audiobooka do osadzenia w pliku M4B."""

    title: str
    author: str | None = None
    cover: str | Path | None = None


def _have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _pitch_shift(path: Path, semitones: float) -> None:
    """Przesuwa wysokosc dzwieku o `semitones` poltonow, zachowujac tempo.

    Ujemna wartosc = nizszy (glebszy) glos. Wymaga ffmpeg. Trick: asetrate
    zmienia wysokosc i tempo o ten sam wspolczynnik, a atempo przywraca tempo.
    """
    if not _have_ffmpeg():
        raise RuntimeError(
            "Zmiana wysokosci glosu (--pitch) wymaga ffmpeg. Zainstaluj ffmpeg."
        )
    # Czestotliwosc probkowania przez ffprobe (dziala dla WAV i MP3).
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        sr = int(proc.stdout.strip())
    except ValueError:
        raise RuntimeError(f"Nie odczytano sample rate dla {path}") from None

    k = 2.0 ** (semitones / 12.0)
    target_sr = max(1, int(round(sr * k)))
    af = f"asetrate={target_sr},aresample={sr},atempo={1.0 / k:.6f}"

    tmp = path.with_suffix(f".pitch{path.suffix}")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-af", af, str(tmp)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg pitch-shift nie powiodl sie:\n{proc.stderr[-1000:]}")
    tmp.replace(path)


def _have_ffprobe() -> bool:
    return shutil.which("ffprobe") is not None


def synthesize_book(
    book: Book,
    backend: TTSBackend,
    out_dir: str | Path,
    opts: SynthOptions | None = None,
    progress=None,
) -> list[tuple[Path, str]]:
    """Syntetyzuje cala ksiazke.

    Zwraca liste (plik_audio, tytul_rozdzialu) — tylko dla rozdzialow, ktore
    realnie wyprodukowaly audio (puste sa pomijane), wiec tytuly sa zgodne
    z plikami.

    `progress` — opcjonalny callable(done, total, label) do raportowania postepu.
    """
    opts = opts or SynthOptions()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = out_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    backend.preflight()

    # Policz wszystkie fragmenty z gory, by raportowac sensowny postep.
    prepared: list[tuple[int, list[str]]] = []
    for ch in book.chapters:
        text = clean_text(ch.text)
        if opts.normalize:
            text = normalize_text(text)
        prepared.append((ch.index, chunk_text(text, opts.max_chars)))

    # Tryb probki: ogranicz do pierwszych N fragmentow (lacznie).
    if opts.max_chunks is not None:
        budget = opts.max_chunks
        trimmed: list[tuple[int, list[str]]] = []
        for idx, chunks in prepared:
            take = chunks[:max(0, budget)]
            trimmed.append((idx, take))
            budget -= len(take)
        prepared = trimmed

    total = sum(len(c) for _, c in prepared) or 1

    done = 0
    chapters_out: list[tuple[Path, str]] = []

    for (idx, chunks), chapter in zip(prepared, book.chapters):
        if not chunks:
            continue
        piece_paths: list[Path] = []
        for j, piece in enumerate(chunks):
            piece_path = chunks_dir / f"ch{idx:03d}_{j:04d}.{backend.audio_ext}"
            if opts.resume and piece_path.exists() and piece_path.stat().st_size > 0:
                # Fragment juz zrobiony w poprzednim przebiegu — pomin.
                piece_paths.append(piece_path)
                done += 1
                if progress:
                    progress(done, total, chapter.title)
                continue
            # Zapis atomowy: najpierw plik tymczasowy, potem zamiana — dzieki
            # czemu --resume nigdy nie zostawia uciętego/uszkodzonego fragmentu.
            tmp_path = piece_path.with_suffix(f".tmp.{backend.audio_ext}")
            backend.synthesize(piece, tmp_path)
            tmp_path.replace(piece_path)
            piece_paths.append(piece_path)
            done += 1
            if progress:
                progress(done, total, chapter.title)

        chapter_file = out_dir / f"ch{idx:03d}.{backend.audio_ext}"
        _concat_audio(piece_paths, chapter_file)
        if opts.pitch:
            _pitch_shift(chapter_file, opts.pitch)
        chapters_out.append((chapter_file, chapter.title))

    if not opts.keep_chunks:
        shutil.rmtree(chunks_dir, ignore_errors=True)

    return chapters_out


def merge_chapters(
    chapter_files: list[Path],
    out_file: str | Path,
    titles: list[str] | None = None,
) -> Path:
    """Laczy pliki rozdzialow w jeden audiobook (z rozdzialami, jesli ffmpeg)."""
    out_file = Path(out_file)
    if not chapter_files:
        raise ValueError("Brak plikow rozdzialow do zlaczenia.")

    if _have_ffmpeg():
        _concat_audio(chapter_files, out_file, titles=titles)
    else:
        # Fallback bez rozdzialow — tylko WAV.
        _concat_wav(chapter_files, out_file)
    return out_file


# --------------------------------------------------------------------------- #
# Laczenie audio — implementacje
# --------------------------------------------------------------------------- #
def _concat_audio(
    parts: list[Path], out_file: Path, titles: list[str] | None = None
) -> None:
    if _have_ffmpeg():
        _concat_ffmpeg(parts, out_file, titles=titles)
    else:
        _concat_wav(parts, out_file)


def _concat_ffmpeg(
    parts: list[Path], out_file: Path, titles: list[str] | None = None
) -> None:
    """Laczy przez ffmpeg (concat demuxer). Bezstratnie dla zgodnych kodekow."""
    list_file = out_file.with_suffix(".txt")
    list_file.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(out_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        # Re-koduj, gdy "copy" zawiedzie (np. rozne parametry strumieni).
        proc = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_file), str(out_file)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg concat nie powiodl sie:\n{proc.stderr[-1500:]}")


def _concat_wav(parts: list[Path], out_file: Path) -> None:
    """Czysto-pythonowe laczenie plikow WAV o tych samych parametrach."""
    if out_file.suffix.lower() != ".wav":
        out_file = out_file.with_suffix(".wav")

    with wave.open(str(parts[0]), "rb") as first:
        params = first.getparams()

    with wave.open(str(out_file), "wb") as out:
        out.setparams(params)
        for part in parts:
            with wave.open(str(part), "rb") as w:
                if w.getnframes() == 0:
                    continue
                out.writeframes(w.readframes(w.getnframes()))


# --------------------------------------------------------------------------- #
# Eksport M4B (audiobook z rozdzialami, metadanymi i okladka)
# --------------------------------------------------------------------------- #
def _probe_duration(path: Path) -> float:
    """Zwraca dlugosc pliku audio w sekundach (przez ffprobe)."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe nie odczytal dlugosci {path}:\n{proc.stderr[-500:]}")
    return float(proc.stdout.strip())


def _ffmetadata(titles: list[str], durations: list[float], meta: BookMeta) -> str:
    """Buduje plik FFMETADATA z globalnymi tagami i znacznikami rozdzialow."""

    def esc(value: str) -> str:
        # W FFMETADATA znaki =, ;, #, \ i nowa linia musza byc poprzedzone '\'.
        for ch in ("\\", "=", ";", "#"):
            value = value.replace(ch, "\\" + ch)
        return value.replace("\n", "\\\n")

    lines = [";FFMETADATA1", f"title={esc(meta.title)}", f"album={esc(meta.title)}"]
    if meta.author:
        lines.append(f"artist={esc(meta.author)}")

    start_ms = 0
    for title, dur in zip(titles, durations):
        end_ms = start_ms + int(round(dur * 1000))
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start_ms}",
            f"END={end_ms}",
            f"title={esc(title)}",
        ]
        start_ms = end_ms
    return "\n".join(lines) + "\n"


def export_m4b(
    chapter_files: list[Path],
    out_file: str | Path,
    titles: list[str],
    meta: BookMeta,
) -> Path:
    """Sklada pliki rozdzialow w audiobook .m4b (AAC) z rozdzialami i okladka.

    Wymaga ffmpeg i ffprobe. Zwraca sciezke do gotowego pliku .m4b.
    """
    if not chapter_files:
        raise ValueError("Brak plikow rozdzialow do eksportu.")
    if not (_have_ffmpeg() and _have_ffprobe()):
        raise RuntimeError(
            "Eksport M4B wymaga ffmpeg i ffprobe (pakiet ffmpeg). "
            "Zainstaluj: https://ffmpeg.org"
        )

    out_file = Path(out_file).with_suffix(".m4b")
    durations = [_probe_duration(p) for p in chapter_files]

    list_file = out_file.with_suffix(".concat.txt")
    list_file.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in chapter_files), encoding="utf-8"
    )
    meta_file = out_file.with_suffix(".ffmeta.txt")
    meta_file.write_text(_ffmetadata(titles, durations, meta), encoding="utf-8")

    cover = Path(meta.cover) if meta.cover else None

    # Wejscia: 0=audio(concat), 1=ffmetadata, [2=okladka]
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-i", str(meta_file),
    ]
    if cover:
        cmd += ["-i", str(cover)]

    cmd += ["-map", "0:a", "-map_metadata", "1"]
    if cover:
        cmd += ["-map", "2:v", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
    cmd += [
        "-c:a", "aac", "-b:a", "64k",
        "-movflags", "+faststart",
        "-f", "mp4", str(out_file),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    meta_file.unlink(missing_ok=True)
    if proc.returncode != 0 or not out_file.exists():
        raise RuntimeError(f"Eksport M4B nie powiodl sie:\n{proc.stderr[-1500:]}")
    return out_file
