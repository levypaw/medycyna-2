"""Testy fabryki TTS i walidacji backendow (bez ladowania ciezkich modeli)."""

import pytest

from pdf_audiobook.tts import (
    ElevenLabsBackend,
    PiperBackend,
    TTSError,
    XTTSBackend,
    build_backend,
)


def test_build_backend_piper():
    b = build_backend("piper", voice="glos.onnx", length_scale=1.2)
    assert isinstance(b, PiperBackend)
    assert b.length_scale == 1.2


def test_build_backend_xtts():
    b = build_backend("xtts", voice="ref.wav", language="pl", speed=1.1)
    assert isinstance(b, XTTSBackend)
    assert b.language == "pl"
    assert b.speed == 1.1
    assert b.audio_ext == "wav"


def test_build_backend_elevenlabs():
    b = build_backend("elevenlabs", voice="voice_id_123")
    assert isinstance(b, ElevenLabsBackend)


def test_build_backend_unknown_lists_options():
    with pytest.raises(TTSError) as exc:
        build_backend("nieistniejacy", voice="x")
    msg = str(exc.value)
    assert "piper" in msg and "xtts" in msg and "elevenlabs" in msg


def test_xtts_preflight_missing_reference(tmp_path):
    b = build_backend("xtts", voice=str(tmp_path / "brak.wav"))
    with pytest.raises(TTSError) as exc:
        b.preflight()
    assert "referencyjn" in str(exc.value).lower()
