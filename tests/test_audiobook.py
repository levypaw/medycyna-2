"""Testy logiki skladania audiobooka, ktore nie wymagaja ffmpeg."""

from pdf_audiobook.audiobook import BookMeta, _ffmetadata


def test_ffmetadata_has_header_and_global_tags():
    meta = BookMeta(title="Moja Ksiazka", author="Jan Kowalski")
    out = _ffmetadata(["Rozdzial 1"], [10.0], meta)
    assert out.startswith(";FFMETADATA1")
    assert "title=Moja Ksiazka" in out
    assert "artist=Jan Kowalski" in out
    assert "album=Moja Ksiazka" in out


def test_ffmetadata_chapter_times_are_sequential_ms():
    meta = BookMeta(title="K")
    out = _ffmetadata(["A", "B"], [1.5, 2.0], meta)
    # 1.5s -> 1500ms; drugi rozdzial startuje tam, gdzie konczy sie pierwszy.
    assert "START=0" in out
    assert "END=1500" in out
    assert "START=1500" in out
    assert "END=3500" in out
    assert out.count("[CHAPTER]") == 2


def test_ffmetadata_escapes_special_chars():
    meta = BookMeta(title="A=B;C#D")
    out = _ffmetadata(["X"], [1.0], meta)
    assert "title=A\\=B\\;C\\#D" in out


def test_ffmetadata_omits_artist_when_no_author():
    out = _ffmetadata(["X"], [1.0], BookMeta(title="K"))
    assert "artist=" not in out
