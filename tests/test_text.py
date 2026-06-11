"""Testy logiki czysto-pythonowej (bez zewnetrznych narzedzi/silnikow)."""

from pdf_audiobook.chunk import chunk_text, split_sentences
from pdf_audiobook.clean import clean_text


def test_dehyphenation_joins_broken_words():
    raw = "To jest infor-\nmacja o czyms."
    assert "informacja" in clean_text(raw)


def test_single_newlines_become_spaces_but_paragraphs_stay():
    raw = "Pierwsza linia\ndruga linia.\n\nNowy akapit."
    out = clean_text(raw)
    assert "Pierwsza linia druga linia." in out
    assert "\n\n" in out


def test_page_number_lines_removed():
    raw = "Tekst rozdzialu.\n\n42\n\nDalszy tekst."
    out = clean_text(raw)
    assert "\n42\n" not in out
    assert "Dalszy tekst." in out


def test_split_sentences_polish():
    text = "Pierwsze zdanie. Drugie zdanie! Trzecie zdanie?"
    assert split_sentences(text) == [
        "Pierwsze zdanie.",
        "Drugie zdanie!",
        "Trzecie zdanie?",
    ]


def test_chunk_respects_max_chars():
    sentences = " ".join(f"Zdanie numer {i}." for i in range(200))
    chunks = chunk_text(sentences, max_chars=100)
    assert chunks
    assert all(len(c) <= 100 for c in chunks)


def test_long_sentence_split_under_limit():
    # Zdanie dluzsze niz limit silnika musi zostac podzielone (XTTS=224).
    long_sentence = (
        "Szedł przez las, mijał drzewa, krzewy i kamienie, "
        + "rozglądał się uważnie, " * 20
        + "aż dotarł do celu."
    )
    chunks = chunk_text(long_sentence, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_hard_split_when_no_punctuation():
    # Brak interpunkcji — dzielenie po slowach, wciaz <= limit.
    chunks = chunk_text("slowo " * 100, max_chars=50)
    assert all(len(c) <= 50 for c in chunks)


def test_heading_becomes_separate_paragraph():
    raw = "Rozdział I. Przybycie\nDziało się to w osadzie. Spokojny dzień."
    out = clean_text(raw)
    # Naglowek konczy sie kropka i jest oddzielony od tresci pusta linia.
    assert "Przybycie." in out
    assert "\n\n" in out
    chunks = chunk_text(out, 600)
    assert chunks[0].startswith("Rozdział I. Przybycie")
    assert "Działo" not in chunks[0]


def test_chunk_breaks_on_paragraphs():
    text = "Akapit jeden.\n\nAkapit dwa."
    chunks = chunk_text(text, max_chars=1000)
    assert chunks == ["Akapit jeden.", "Akapit dwa."]
