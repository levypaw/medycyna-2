"""Testy heurystyki front-matter (EPUB i PDF), bez ebooklib/pymupdf."""

from pdf_audiobook.extract import (
    _blank_leading_front_matter,
    _is_front_matter,
    _looks_like_front_matter_page,
)


def test_pdf_long_code_page_is_front_matter():
    assert _looks_like_front_matter_page("78121415585220\nSaga: Odrodzenie")
    assert not _looks_like_front_matter_page("Las szumiał nad doliną. " * 60)


def test_blank_leading_front_matter_keeps_indices_and_content():
    pages = [
        "78121415585220 Saga: Odrodzenie",
        "Tytuł oryginału: X. ISBN 978. Copyright. Wydawnictwo.",
        "Rozdział I. Las szumiał cicho nad doliną i niczego nie zwiastował.",
        "Dalsza tresc z liczba 78121415585220 w srodku.",
    ]
    out = _blank_leading_front_matter(pages)
    assert out[0] == "" and out[1] == ""          # strony tytulowe wyczyszczone
    assert out[2].startswith("Rozdział I.")        # tresc zachowana
    assert "78121415585220" in out[3]              # kod w srodku NIE czyszczony
    assert len(out) == len(pages)                  # indeksy stron zachowane


def test_front_matter_by_filename():
    assert _is_front_matter("OEBPS/cover.xhtml", "cokolwiek")
    assert _is_front_matter("nav.xhtml", "Spis treści")
    assert _is_front_matter("text/copyright.xhtml", "blah")


def test_front_matter_by_boilerplate_markers():
    text = "Tytuł oryginału: The Saga. ISBN 978-83-000. Wydawnictwo XYZ."
    assert _is_front_matter("text/sec0002.xhtml", text)


def test_real_chapter_is_not_front_matter():
    text = "Działo się to jeszcze w dawnych czasach. " * 60
    assert not _is_front_matter("text/chapter01.xhtml", text)


def test_short_non_boilerplate_is_not_front_matter():
    assert not _is_front_matter("text/sec1.xhtml", "Krótki wstęp do opowieści.")
