"""Provider failure tests for the production voice boundary."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from voice_gateway.providers import ElevenLabsTTSService, GroqSTTService
from voice_gateway.tts import MockTTSService
from services.config import settings


@pytest.mark.asyncio
async def test_stt_without_provider_fails_without_fabricating_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.groq, "api_key", "")
    with pytest.raises(RuntimeError, match="provider"):
        await GroqSTTService().transcribe(b"[SYNTHETIC_AUDIO]", "en")


@pytest.mark.asyncio
async def test_tts_without_provider_fails_without_fabricating_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.elevenlabs, "api_key", "")
    with pytest.raises(RuntimeError, match="provider"):
        await ElevenLabsTTSService().synthesize("[SYNTHETIC_TEST_CASE] hello", "en")


@pytest.mark.asyncio
async def test_elevenlabs_fallback_to_kokoro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.elevenlabs, "api_key", "")
    mock_fallback = MockTTSService()
    service = ElevenLabsTTSService(fallback_tts=mock_fallback)
    res = await service.synthesize("Hello Vadi", "hi")
    assert res == b"MOCK_KOKORO_AUDIO_BYTES"
    assert mock_fallback.last_synthesized_text == "Hello Vadi"


@pytest.mark.asyncio
async def test_voice_settings_parameters_defaults() -> None:
    assert settings.elevenlabs.voice_id in ("2EiwWnXFnvU5JabPnv8n", "EXAVITQu4vr4xnSDxMaL", "9BWtsMINqrJLrRacOk9x")
    assert settings.elevenlabs.speed == 1.0
    assert settings.elevenlabs.stability in (0.5, 0.7)
    assert settings.voice.kokoro_profile_hi == "hi_female"
    assert settings.voice.piper_model_pa == "models/pa_in.onnx"
