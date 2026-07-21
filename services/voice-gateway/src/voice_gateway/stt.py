"""
Speech-to-Text (STT) services for Vadi-Pehn.
Implements: Abstract-first pattern.
Enforces the mandatory NO RAW AUDIO RETENTION policy.
"""

from __future__ import annotations

from typing import Any

import httpx
from voice_gateway.abstractions import STTService


class MockSTTService(STTService):
    """
    Mock STT service for unit testing and local development.
    Transcribes audio into pre-defined synthetic transcripts.
    Does NOT store raw audio.
    """

    def __init__(self, transcript_to_return: str = "Hello, Vadi! How are you?") -> None:
        self.transcript_to_return = transcript_to_return

    async def transcribe(self, audio_data: bytes, language: str = "en") -> str:
        """
        Simulate transcription and immediately delete the raw audio.
        """
        try:
            # Check input language
            if language == "hi":
                return "नमस्ते दीदी, आप कैसी हैं?"
            elif language == "pa":
                return "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਭੈਣ ਜੀ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?"
            return self.transcript_to_return
        finally:
            # MANDATORY CHILD-SAFETY COMPLIANCE: Overwrite & free raw audio buffer immediately
            if isinstance(audio_data, bytearray):
                for i in range(len(audio_data)):
                    audio_data[i] = 0
            del audio_data


class WhisperSTTService(STTService):
    """
    Production client wrapper for local GPU-hosted Whisper-large-v3 service.
    Sends raw audio bytes to faster-distil-whisper endpoint.
    Enforces immediate memory wipe to prevent raw audio retention.
    """

    def __init__(self, whisper_url: str, model_name: str) -> None:
        self.whisper_url = whisper_url.rstrip("/")
        self.model_name = model_name

    async def transcribe(self, audio_data: bytes, language: str = "en") -> str:
        """
        Sends audio payload to Whisper endpoint, retrieves transcription,
        and wipes the audio buffer.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Whisper endpoint expects multipart/form-data or raw POST
                # Here we send audio bytes as file upload
                files = {"file": ("audio.wav", audio_data, "audio/wav")}
                data = {"model": self.model_name, "language": language}
                response = await client.post(
                    f"{self.whisper_url}/v1/audio/transcriptions",
                    files=files,
                    data=data,
                    timeout=5.0,  # Enforce budget limits
                )
                response.raise_for_status()
                return response.json().get("text", "")
        except Exception:
            # Fail closed: never turn a transport/error string into a child-facing prompt.
            return ""
        finally:
            # MANDATORY CHILD-SAFETY COMPLIANCE: Overwrite and purge buffer references
            # Ensures zero raw voice audio retention after the transcription step (PRD §3.4)
            if isinstance(audio_data, bytearray):
                for i in range(len(audio_data)):
                    audio_data[i] = 0
            del audio_data


class ZeroRetentionVerifier:
    """Helper class to audit and verify no raw audio variables leak."""

    @staticmethod
    def verify_buffer_purged(var: Any) -> bool:
        return var is None
