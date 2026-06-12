"""Testy fabryki TTS i walidacji backendow (bez ladowania ciezkich modeli)."""

import pytest

from pdf_audiobook.tts import (
    ElevenLabsBackend,
    EspeakBackend,
    PiperBackend,
    TTSError,
    XTTSBackend,
    build_backend,
)


def test_build_backend_espeak():
    b = build_backend("espeak", language="pl", speed_wpm=170)
    assert isinstance(b, EspeakBackend)
    assert b.voice == "pl"
    assert b.speed == 170
    assert b.audio_ext == "wav"


def test_build_backend_piper():
    b = build_backend("piper", voice="glos.onnx", length_scale=1.2)
    assert isinstance(b, PiperBackend)
    assert b.length_scale == 1.2


def test_build_backend_xtts():
    b = build_backend("xtts", voice="ref.wav", language="pl", speed=1.1,
                      temperature=0.5)
    assert isinstance(b, XTTSBackend)
    assert b.language == "pl"
    assert b.speed == 1.1
    assert b.temperature == 0.5
    assert b.audio_ext == "wav"
    assert len(b.speaker_wavs) == 1


def test_build_backend_xtts_multi_reference():
    b = build_backend("xtts", voice="a.wav, b.wav , c.wav")
    assert [p.name for p in b.speaker_wavs] == ["a.wav", "b.wav", "c.wav"]


def test_build_backend_elevenlabs():
    b = build_backend("elevenlabs", voice="voice_id_123")
    assert isinstance(b, ElevenLabsBackend)


def test_build_backend_unknown_lists_options():
    with pytest.raises(TTSError) as exc:
        build_backend("nieistniejacy", voice="x")
    msg = str(exc.value)
    assert all(x in msg for x in ("espeak", "piper", "xtts", "elevenlabs"))


def test_xtts_preflight_missing_reference(tmp_path):
    b = build_backend("xtts", voice=str(tmp_path / "brak.wav"))
    with pytest.raises(TTSError) as exc:
        b.preflight()
    assert "referencyjn" in str(exc.value).lower()
