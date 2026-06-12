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
from .audiobook import (
    BookMeta,
    SynthOptions,
    export_m4b,
    merge_chapters,
    synthesize_book,
)
from .chunk import chunk_text
from .clean import clean_text
from .extract import ExtractionError, extract
from .normalize import normalize_text
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
                   choices=["espeak", "piper", "xtts", "elevenlabs"],
                   help="Silnik TTS (domyslnie: piper; espeak = test bez konfiguracji)")
    p.add_argument("--voice",
                   help="Glos wg backendu: sciezka .onnx (piper) lub voice_id "
                        "(elevenlabs). Dla xtts: plik .wav, kilka plikow po "
                        "przecinku, albo katalog z *.wav (wiele probek = "
                        "wierniejszy klon). Niewymagany dla espeak")
    p.add_argument("--language", default="pl",
                   help="XTTS: jezyk syntezy (domyslnie pl)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="XTTS: tempo mowy (1.0 = normalne)")
    p.add_argument("--pitch", type=float, default=0.0,
                   help="Przesuniecie wysokosci glosu w poltonach (ujemne = glebszy, "
                        "np. -2). Wymaga ffmpeg")
    p.add_argument("--temperature", type=float, default=0.65,
                   help="XTTS: nizsza = stabilniej/mniej bledow, wyzsza = wiecej "
                        "ekspresji (domyslnie 0.65; sprobuj 0.5)")
    p.add_argument("--model-id", default="eleven_multilingual_v2",
                   help="ElevenLabs: model API (eleven_multilingual_v2 = najlepsza "
                        "jakosc, 1 kredyt/znak; eleven_flash_v2_5 = tanszy, "
                        "0.5 kredytu/znak)")
    p.add_argument("--estimate", action="store_true",
                   help="Policz znaki/fragmenty i szacunkowy koszt ElevenLabs, "
                        "bez syntezy")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"],
                   help="XTTS: urzadzenie (auto wykrywa; mps = GPU Apple Silicon)")
    p.add_argument("--length-scale", type=float, default=1.05,
                   help="Piper: tempo mowy; >1 wolniej/dostojniej (domyslnie 1.05)")
    p.add_argument("--max-chars", type=int, default=None,
                   help="Maks. dlugosc fragmentu wysylanego do TTS (domyslnie: "
                        "200 dla xtts ze wzgledu na limit 224 znakow, 600 dla reszty)")
    p.add_argument("--ocr", default="auto", choices=["auto", "force", "off"],
                   help="OCR dla PDF: auto=tylko skany, force=wszystkie strony, off "
                        "(domyslnie auto)")
    p.add_argument("--ocr-lang", default="pol",
                   help="Jezyk(i) OCR Tesseract, np. 'pol' lub 'pol+eng' (domyslnie pol)")
    p.add_argument("--ocr-dpi", type=int, default=300,
                   help="Rozdzielczosc renderowania strony do OCR (domyslnie 300)")
    p.add_argument("--merge", action="store_true",
                   help="Polacz rozdzialy w jeden plik audiobooka")
    p.add_argument("--m4b", action="store_true",
                   help="Eksportuj audiobook .m4b z rozdzialami i metadanymi (ffmpeg)")
    p.add_argument("--cover", help="Sciezka do okladki (jpg/png) dla M4B")
    p.add_argument("--author", help="Autor ksiazki (metadane M4B)")
    p.add_argument("--title", help="Tytul (nadpisuje wykryty; metadane/nazwa pliku)")
    p.add_argument("--no-normalize", dest="normalize", action="store_false",
                   help="Wylacz normalizacje tekstu PL (skroty, liczby, l. rzymskie)")
    p.add_argument("--keep-chunks", action="store_true",
                   help="Nie usuwaj posrednich plikow fragmentow")
    p.add_argument("--resume", action="store_true",
                   help="Wznow: pomijaj fragmenty juz zsyntetyzowane w tym katalogu "
                        "(dla dlugich ksiazek — przezyje przerwanie)")
    p.add_argument("--max-chunks", type=int, default=None,
                   help="Tryb probki: syntetyzuj tylko N fragmentow "
                        "(np. 20 ~ 2 strony) — szybki test na duzej ksiazce")
    p.add_argument("--skip-chunks", type=int, default=0,
                   help="Pomin pierwsze N fragmentow (np. strony tytulowe/copyright "
                        "EPUB). Laczy sie z --max-chunks w okno probki")
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

    if args.title:
        book.title = args.title

    print(f"Tytul: {book.title}", file=sys.stderr)
    print(f"Rozdzialow: {len(book.chapters)}", file=sys.stderr)

    if args.dry_run:
        for ch in book.chapters:
            text = clean_text(ch.text)
            if args.normalize:
                text = normalize_text(text)
            print(f"\n=== [{ch.index}] {ch.title} ===\n{text[:500]}...")
        return 0

    if args.estimate:
        max_chars = args.max_chars or (200 if args.backend == "xtts" else 600)
        total_chars = 0
        total_chunks = 0
        for ch in book.chapters:
            text = clean_text(ch.text)
            if args.normalize:
                text = normalize_text(text)
            chunks = chunk_text(text, max_chars)
            total_chunks += len(chunks)
            total_chars += sum(len(c) for c in chunks)
        print(f"Znakow do syntezy (po normalizacji): {total_chars:,}")
        print(f"Fragmentow: {total_chunks:,} (max {max_chars} znakow)")
        print(f"Szacowane audio: ~{total_chars / 54000:.1f} godz. "
              "(przy ~15 znakach/sek)")
        print("Szacunek ElevenLabs (kredyty ~= znaki):")
        print(f"  eleven_flash_v2_5      : ~{total_chars // 2:,} kredytow")
        print(f"  eleven_multilingual_v2 : ~{total_chars:,} kredytow")
        print("Plany (orientacyjnie): Creator ~100k kredytow/$22, "
              "Pro ~500k/$99, Scale ~2M/$330 — zweryfikuj na "
              "elevenlabs.io/pricing")
        return 0

    if not args.voice and args.backend != "espeak":
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
            temperature=args.temperature,
            model_id=args.model_id,
            device=None if args.device == "auto" else args.device,
        )
        # XTTS ma twardy limit 224 znakow na fragment dla PL -> bezpieczne 200.
        max_chars = args.max_chars
        if max_chars is None:
            max_chars = 200 if args.backend == "xtts" else 600
        opts = SynthOptions(
            max_chars=max_chars,
            keep_chunks=args.keep_chunks,
            normalize=args.normalize,
            pitch=args.pitch,
            resume=args.resume,
            max_chunks=args.max_chunks,
            skip_chunks=args.skip_chunks,
        )
        chapters_out = synthesize_book(
            book, backend, args.out_dir, opts, progress=_progress
        )
    except TTSError as exc:
        print(f"\nBlad TTS: {exc}", file=sys.stderr)
        return 3

    print(f"Zapisano {len(chapters_out)} plik(ow) rozdzialow w {args.out_dir}",
          file=sys.stderr)

    chapter_files = [p for p, _ in chapters_out]
    titles = [t for _, t in chapters_out]

    if args.m4b and chapter_files:
        meta = BookMeta(title=book.title, author=args.author, cover=args.cover)
        try:
            out_file = Path(args.out_dir) / book.title
            m4b = export_m4b(chapter_files, out_file, titles, meta)
        except (RuntimeError, ValueError) as exc:
            print(f"\nBlad eksportu M4B: {exc}", file=sys.stderr)
            return 4
        print(f"Audiobook (M4B): {m4b}", file=sys.stderr)
    elif args.merge and chapter_files:
        ext = chapter_files[0].suffix
        out_file = Path(args.out_dir) / f"{book.title}{ext}"
        merged = merge_chapters(chapter_files, out_file, titles=titles)
        print(f"Audiobook: {merged}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
