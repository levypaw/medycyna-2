"""Testy modulu OCR, ktore nie wymagaja zainstalowanego Tesseracta."""

from pdf_audiobook import ocr


def test_ocr_available_returns_bool():
    assert isinstance(ocr.ocr_available(), bool)


def test_assert_available_raises_when_tesseract_missing():
    """Bez binarki/modelu assert_available powinno rzucic czytelny OCRError."""
    if ocr.ocr_available():
        # W srodowisku z dzialajacym OCR ten przypadek nie ma zastosowania.
        return
    try:
        ocr.assert_available("pol")
    except ocr.OCRError as exc:
        assert "OCR" in str(exc) or "tesseract" in str(exc).lower()
    else:
        raise AssertionError("Oczekiwano OCRError, gdy OCR niedostepny")


def test_min_text_chars_threshold_is_sane():
    assert 0 < ocr.MIN_TEXT_CHARS < 200
