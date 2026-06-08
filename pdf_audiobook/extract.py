"""Ekstrakcja tekstu z roznych formatow ksiazek.

Obslugiwane:
    .pdf            -> PyMuPDF (fitz); OCR poza zakresem tej wersji
    .epub           -> ebooklib + BeautifulSoup
    .mobi / .azw3   -> konwersja przez `ebook-convert` (Calibre) do EPUB, potem jak epub
    .txt            -> wprost

Kazda funkcja zwraca liste rozdzialow: list[Chapter]. Jesli format nie niesie
informacji o rozdzialach, zwracany jest jeden rozdzial z calym tekstem.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chapter:
    """Pojedynczy rozdzial ksiazki."""

    title: str
    text: str
    index: int = 0


@dataclass
class Book:
    """Cala ksiazka po ekstrakcji."""

    title: str
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(ch.text for ch in self.chapters)


class ExtractionError(RuntimeError):
    """Blad podczas wyciagania tekstu z pliku."""


# --------------------------------------------------------------------------- #
# Dyspozytor wg rozszerzenia
# --------------------------------------------------------------------------- #
def extract(
    path: str | Path,
    *,
    ocr: str = "auto",
    ocr_lang: str = "pol",
    ocr_dpi: int = 300,
) -> Book:
    """Wybiera ekstraktor na podstawie rozszerzenia pliku.

    OCR (tylko PDF):
        ocr="auto"  — OCR tylko stron bez warstwy tekstowej (jesli dostepny),
        ocr="force" — OCR wszystkich stron (ignoruje warstwe tekstowa),
        ocr="off"   — bez OCR.
    """
    path = Path(path)
    if not path.exists():
        raise ExtractionError(f"Plik nie istnieje: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path, ocr=ocr, ocr_lang=ocr_lang, ocr_dpi=ocr_dpi)
    if suffix == ".epub":
        return _extract_epub(path)
    if suffix in {".mobi", ".azw", ".azw3", ".fb2", ".lit", ".pdb"}:
        return _extract_via_calibre(path)
    if suffix == ".txt":
        return _extract_txt(path)
    raise ExtractionError(
        f"Nieobslugiwany format: {suffix}. "
        "Obsluga: .pdf, .epub, .mobi, .azw3, .txt"
    )


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _extract_pdf(
    path: Path, *, ocr: str = "auto", ocr_lang: str = "pol", ocr_dpi: int = 300
) -> Book:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - zalezne od srodowiska
        raise ExtractionError(
            "Do PDF potrzebny jest PyMuPDF. Zainstaluj: pip install pymupdf"
        ) from exc

    from . import ocr as ocr_mod

    doc = fitz.open(path)
    pages = ["" if ocr == "force" else page.get_text("text") for page in doc]

    needs_ocr = ocr == "force" or (
        ocr == "auto"
        and any(len(p.strip()) < ocr_mod.MIN_TEXT_CHARS for p in pages)
    )

    if needs_ocr:
        if not ocr_mod.ocr_available():
            if all(not p.strip() for p in pages):
                doc.close()
                raise ExtractionError(
                    "Brak warstwy tekstowej (skan), a OCR nie jest dostepny. "
                    "Zainstaluj: pip install pytesseract pillow oraz Tesseract "
                    "z modelem 'pol'. Szczegoly: pdf_audiobook/ocr.py"
                )
            # Czesc stron ma tekst — kontynuuj bez OCR pozostalych.
        else:
            ocr_mod.assert_available(ocr_lang)
            for i, page in enumerate(doc):
                if ocr == "force" or len(pages[i].strip()) < ocr_mod.MIN_TEXT_CHARS:
                    pages[i] = ocr_mod.ocr_page(page, lang=ocr_lang, dpi=ocr_dpi)

    if all(not p.strip() for p in pages):
        doc.close()
        raise ExtractionError(
            "Nie wyciagnieto tekstu — to prawdopodobnie pusty lub uszkodzony plik."
        )

    # Usun naglowki/stopki powtarzajace sie na wielu stronach.
    pages = _strip_running_headers(pages)

    title = (doc.metadata or {}).get("title") or path.stem
    chapters = _chapters_from_toc(doc, pages) or [
        Chapter(title=title, text="\n".join(pages), index=0)
    ]
    doc.close()
    return Book(title=title, chapters=chapters)


def _chapters_from_toc(doc, pages: list[str]) -> list[Chapter]:
    """Buduje rozdzialy ze spisu tresci PDF, jesli jest dostepny."""
    toc = doc.get_toc(simple=True)  # [[level, title, page], ...]
    if not toc:
        return []

    # Bierzemy tylko wpisy najwyzszego poziomu jako granice rozdzialow.
    top = [(t, p - 1) for lvl, t, p in toc if lvl == 1 and 0 <= p - 1 < len(pages)]
    if len(top) < 2:
        return []

    chapters: list[Chapter] = []
    for i, (chap_title, start) in enumerate(top):
        end = top[i + 1][1] if i + 1 < len(top) else len(pages)
        text = "\n".join(pages[start:end]).strip()
        if text:
            chapters.append(Chapter(title=chap_title.strip(), text=text, index=i))
    return chapters


def _strip_running_headers(pages: list[str]) -> list[str]:
    """Wykrywa i usuwa linie powtarzajace sie na wielu stronach (naglowki/stopki)."""
    if len(pages) < 4:
        return pages

    from collections import Counter

    first_lines: Counter[str] = Counter()
    last_lines: Counter[str] = Counter()
    for p in pages:
        lines = [ln.strip() for ln in p.splitlines() if ln.strip()]
        if not lines:
            continue
        first_lines[lines[0]] += 1
        last_lines[lines[-1]] += 1

    threshold = max(3, len(pages) // 4)
    repeated = {ln for ln, c in first_lines.items() if c >= threshold}
    repeated |= {ln for ln, c in last_lines.items() if c >= threshold}

    cleaned = []
    for p in pages:
        lines = p.splitlines()
        lines = [ln for ln in lines if ln.strip() not in repeated]
        cleaned.append("\n".join(lines))
    return cleaned


# --------------------------------------------------------------------------- #
# EPUB
# --------------------------------------------------------------------------- #
def _extract_epub(path: Path) -> Book:
    try:
        from ebooklib import epub
        import ebooklib
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "Do EPUB potrzebne: pip install ebooklib beautifulsoup4"
        ) from exc

    book = epub.read_epub(str(path))
    title_meta = book.get_metadata("DC", "title")
    title = title_meta[0][0] if title_meta else path.stem

    chapters: list[Chapter] = []
    for i, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text("\n").strip()
        if not text:
            continue
        heading = soup.find(["h1", "h2", "h3"])
        chap_title = heading.get_text(" ").strip() if heading else f"Rozdzial {i + 1}"
        chapters.append(Chapter(title=chap_title, text=text, index=len(chapters)))

    if not chapters:
        raise ExtractionError("Pusty EPUB — brak tresci tekstowej.")
    return Book(title=title, chapters=chapters)


# --------------------------------------------------------------------------- #
# MOBI / inne — przez Calibre
# --------------------------------------------------------------------------- #
def _extract_via_calibre(path: Path) -> Book:
    """Konwertuje do EPUB przy pomocy `ebook-convert`, potem czyta jak EPUB."""
    if shutil.which("ebook-convert") is None:
        raise ExtractionError(
            f"Format {path.suffix} wymaga Calibre (`ebook-convert`). "
            "Zainstaluj Calibre: https://calibre-ebook.com/download"
        )

    with tempfile.TemporaryDirectory() as tmp:
        epub_path = Path(tmp) / (path.stem + ".epub")
        proc = subprocess.run(
            ["ebook-convert", str(path), str(epub_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not epub_path.exists():
            raise ExtractionError(
                f"ebook-convert nie powiodlo sie:\n{proc.stderr[-2000:]}"
            )
        return _extract_epub(epub_path)


# --------------------------------------------------------------------------- #
# TXT
# --------------------------------------------------------------------------- #
def _extract_txt(path: Path) -> Book:
    text = path.read_text(encoding="utf-8", errors="replace")
    return Book(title=path.stem, chapters=[Chapter(title=path.stem, text=text)])
