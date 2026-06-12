"""Testy logiki skladania audiobooka, ktore nie wymagaja ffmpeg."""

import wave

from pdf_audiobook.audiobook import (
    BookMeta,
    SynthOptions,
    _ffmetadata,
    synthesize_book,
)
from pdf_audiobook.extract import Book, Chapter
from pdf_audiobook.tts import TTSBackend


class _CountingBackend(TTSBackend):
    """Atrapa TTS: zapisuje krotki, poprawny WAV i liczy wywolania."""

    audio_ext = "wav"

    def __init__(self):
        self.calls = 0

    def synthesize(self, text, out_path):
        self.calls += 1
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(b"\x00\x00" * 100)


def test_max_chunks_limits_synthesis(tmp_path):
    book = Book(title="T", chapters=[
        Chapter(title="R1", text="A. B. C. D. E. F. G. H.", index=0),
    ])
    backend = _CountingBackend()
    opts = SynthOptions(max_chars=2, max_chunks=3)
    synthesize_book(book, backend, tmp_path, opts)
    assert backend.calls == 3


def test_resume_skips_done_chunks(tmp_path):
    book = Book(title="T", chapters=[
        Chapter(title="R1", text="Zdanie jedno. Zdanie dwa. Zdanie trzy.", index=0),
    ])
    backend = _CountingBackend()
    # keep_chunks=True symuluje fragmenty zachowane z poprzedniego przebiegu.
    opts = SynthOptions(max_chars=20, resume=True, keep_chunks=True)

    synthesize_book(book, backend, tmp_path, opts)
    first = backend.calls
    assert first > 0

    # Drugi przebieg z --resume: fragmenty istnieja, brak nowych syntez.
    synthesize_book(book, backend, tmp_path, opts)
    assert backend.calls == first


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
