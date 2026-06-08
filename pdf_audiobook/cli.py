"""Interfejs wiersza polecen.

Przyklady:
    # Lokalnie, Piper (zalecane, offline):
    python -m pdf_audiobook ksiazka.pdf -o out/ \\
        --backend piper --voice pl_PL-darkman-medium.onnx

    # Chmura, ElevenLabs (najlepsza jakosc; ELEVENLABS_API_KEY w srodowisku):
    python -m pdf_audiobook ksiazka.mobi -o out/ \\
        --backend elevenlabs --voice <voice_id>

    # Sam podglad wyciagnietego tekstu, bez syntezy:
    python -m pdf_audiobook ksiazka.epub --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .audiobook import SynthOptions, merge_chapters, synthesize_book
from .clean import clean_text
from .extract import ExtractionError, extract
from .tts import TTSError, build_backend


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf_audiobook",
        description="Zamien ksiazke (PDF/MOBI/EPUB/TXT) na audiobooka glosem lektora.",
    )
    p.add_argument("input", help="Sciezka do pliku ksiazki (.pdf/.epub/.mobi/.txt)")
    p.add_argument("-o", "--out-dir", default="audiobook_out",
                   help="Katalog wyjsciowy (domyslnie: audiobook_out)")
    p.add_argument("--backend", default="piper",
                   choices=["piper", "xtts", "elevenlabs"],
                   help="Silnik TTS (domyslnie: piper)")
    p.add_argument("--voice",
                   help="Glos wg backendu: sciezka .onnx (piper), plik referencyjny "
                        ".wav (xtts) lub voice_id (elevenlabs)")
    p.add_argument("--language", default="pl",
                   help="XTTS: jezyk syntezy (domyslnie pl)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="XTTS: tempo mowy (1.0 = normalne)")
    p.add_argument("--length-scale", type=float, default=1.05,
                   help="Piper: tempo mowy; >1 wolniej/dostojniej (domyslnie 1.05)")
    p.add_argument("--max-chars", type=int, default=600,
                   help="Maks. dlugosc fragmentu wysylanego do TTS (domyslnie 600)")
    p.add_argument("--ocr", default="auto", choices=["auto", "force", "off"],
                   help="OCR dla PDF: auto=tylko skany, force=wszystkie strony, off "
                        "(domyslnie auto)")
    p.add_argument("--ocr-lang", default="pol",
                   help="Jezyk(i) OCR Tesseract, np. 'pol' lub 'pol+eng' (domyslnie pol)")
    p.add_argument("--ocr-dpi", type=int, default=300,
                   help="Rozdzielczosc renderowania strony do OCR (domyslnie 300)")
    p.add_argument("--merge", action="store_true",
                   help="Polacz rozdzialy w jeden plik audiobooka")
    p.add_argument("--keep-chunks", action="store_true",
                   help="Nie usuwaj posrednich plikow fragmentow")
    p.add_argument("--dry-run", action="store_true",
                   help="Tylko wyciagnij i wyczysc tekst, bez syntezy")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _progress(done: int, total: int, label: str) -> None:
    pct = int(done / total * 100)
    bar = "#" * (pct // 4) + "-" * (25 - pct // 4)
    sys.stderr.write(f"\r[{bar}] {pct:3d}% ({done}/{total}) {label[:40]:<40}")
    sys.stderr.flush()
    if done == total:
        sys.stderr.write("\n")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        book = extract(
            args.input, ocr=args.ocr, ocr_lang=args.ocr_lang, ocr_dpi=args.ocr_dpi
        )
    except ExtractionError as exc:
        print(f"Blad ekstrakcji: {exc}", file=sys.stderr)
        return 2

    print(f"Tytul: {book.title}", file=sys.stderr)
    print(f"Rozdzialow: {len(book.chapters)}", file=sys.stderr)

    if args.dry_run:
        for ch in book.chapters:
            preview = clean_text(ch.text)[:500]
            print(f"\n=== [{ch.index}] {ch.title} ===\n{preview}...")
        return 0

    if not args.voice:
        print("Blad: --voice jest wymagany przy syntezie (sciezka .onnx dla piper, "
              "plik referencyjny .wav dla xtts lub voice_id dla elevenlabs).",
              file=sys.stderr)
        return 2

    try:
        backend = build_backend(
            args.backend,
            voice=args.voice,
            length_scale=args.length_scale,
            language=args.language,
            speed=args.speed,
        )
        opts = SynthOptions(max_chars=args.max_chars, keep_chunks=args.keep_chunks)
        chapter_files = synthesize_book(
            book, backend, args.out_dir, opts, progress=_progress
        )
    except TTSError as exc:
        print(f"\nBlad TTS: {exc}", file=sys.stderr)
        return 3

    print(f"Zapisano {len(chapter_files)} plik(ow) rozdzialow w {args.out_dir}",
          file=sys.stderr)

    if args.merge and chapter_files:
        ext = chapter_files[0].suffix
        out_file = Path(args.out_dir) / f"{book.title}{ext}"
        titles = [ch.title for ch in book.chapters]
        merged = merge_chapters(chapter_files, out_file, titles=titles)
        print(f"Audiobook: {merged}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
