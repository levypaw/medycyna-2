"""OCR dla skanowanych PDF-ow.

Skany nie maja warstwy tekstowej — strona jest obrazem. Renderujemy ja przez
PyMuPDF do bitmapy i rozpoznajemy tekst Tesseractem (z polskim modelem `pol`).

Wymaga:
    * pytesseract + Pillow  ->  pip install pytesseract pillow
    * binarka `tesseract`   ->  https://github.com/tesseract-ocr/tesseract
    * model jezyka polskiego (`pol`):
        Debian/Ubuntu: apt-get install tesseract-ocr tesseract-ocr-pol
        macOS (brew):  brew install tesseract tesseract-lang
"""

from __future__ import annotations

import io

# Ponizej ilu znakow tekstu na stronie uznajemy ja za "pusta" (kandydat do OCR).
MIN_TEXT_CHARS = 20


class OCRError(RuntimeError):
    """Blad konfiguracji lub dzialania OCR."""


def ocr_available() -> bool:
    """Czy dostepne sa pytesseract, Pillow i binarka tesseract."""
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def assert_available(lang: str = "pol") -> None:
    """Rzuca czytelny blad, jesli OCR nie jest gotowy (z podpowiedzia instalacji)."""
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise OCRError(
            "OCR wymaga: pip install pytesseract pillow"
        ) from exc
    try:
        langs = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise OCRError(
            "Nie znaleziono binarki `tesseract`. Zainstaluj Tesseract OCR: "
            "https://github.com/tesseract-ocr/tesseract"
        ) from exc
    # Pojedynczy jezyk lub kilka rozdzielonych '+', np. "pol+eng".
    missing = [code for code in lang.split("+") if code not in langs]
    if missing:
        raise OCRError(
            f"Brak modelu jezyka Tesseract: {', '.join(missing)}. "
            "Zainstaluj (np. apt-get install tesseract-ocr-pol) "
            f"lub wybierz dostepny --ocr-lang. Dostepne: {', '.join(sorted(langs))}"
        )


def ocr_page(page, lang: str = "pol", dpi: int = 300) -> str:
    """Renderuje strone PyMuPDF do obrazu i zwraca rozpoznany tekst."""
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang=lang)
