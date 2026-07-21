"""Provider failure tests for the production voice boundary."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from voice_gateway.providers import ElevenLabsTTSService, GroqSTTService


@pytest.mark.asyncio
async def test_stt_without_provider_fails_without_fabricating_transcript() -> None:
    with pytest.raises(RuntimeError, match="No STT provider"):
        await GroqSTTService().transcribe(b"[SYNTHETIC_AUDIO]", "en")


@pytest.mark.asyncio
async def test_tts_without_provider_fails_without_fabricating_audio() -> None:
    with pytest.raises(RuntimeError, match="No TTS provider"):
        await ElevenLabsTTSService().synthesize("[SYNTHETIC_TEST_CASE] hello", "en")
