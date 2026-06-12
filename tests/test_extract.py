"""Testy heurystyki front-matter EPUB (bez ebooklib)."""

from pdf_audiobook.extract import _is_front_matter


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
