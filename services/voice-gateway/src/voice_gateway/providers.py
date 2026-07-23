"""
Ultra-Low Latency Voice Pipeline Providers for Vadi-Pehn.
Implements: PRD §6 (Voice-First Experience), SD §4.2 (Voice Gateway).
Supports:
  1. Groq Cloud Inference API (Whisper STT sub-100ms & Llama 3.3 70B)
  2. ElevenLabs Low-Latency Streaming TTS & Kokoro/Piper fallback
  3. LiveKit WebRTC SFU Token Provider
  4. Child Safety Constraint: Zero raw voice audio retention (PRD §3.4)
"""

from __future__ import annotations

import io
import logging
import httpx

from services.config import settings
from voice_gateway.abstractions import STTService, TTSService

logger = logging.getLogger(__name__)


class GroqSTTService(STTService):
    """
    Sub-100ms Groq Whisper API STT Service.
    Falls back only to an injected STT provider. It never fabricates a transcript:
    an unavailable STT dependency must stop the turn before it reaches the LLM.
    """

    def __init__(self, fallback_stt: STTService | None = None) -> None:
        self.fallback_stt = fallback_stt

    async def transcribe(self, audio_data: bytes, language: str = "en") -> str:
        if not settings.groq.api_key:
            if self.fallback_stt:
                return await self.fallback_stt.transcribe(audio_data, language)
            raise RuntimeError("No STT provider is configured")

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                files = {
                    "file": ("audio.wav", io.BytesIO(audio_data), "audio/wav")
                }
                data = {
                    "model": settings.groq.stt_model,
                    "language": language[:2],
                    "response_format": "json"
                }
                headers = {"Authorization": f"Bearer {settings.groq.api_key}"}

                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    files=files,
                    data=data,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                return result.get("text", "").strip()
        except Exception as exc:
            logger.warning("Groq STT call failed, using fallback: %s", exc)
            if self.fallback_stt:
                return await self.fallback_stt.transcribe(audio_data, language)
            raise RuntimeError("STT provider unavailable") from exc


class ElevenLabsTTSService(TTSService):
    """
    Ultra-Realistic Low-Latency ElevenLabs Streaming TTS Service.
    Falls back only to an injected TTS provider. It never emits fabricated audio.
    """

    def __init__(self, fallback_tts: TTSService | None = None) -> None:
        self.fallback_tts = fallback_tts

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        if not settings.elevenlabs.api_key:
            if self.fallback_tts:
                return await self.fallback_tts.synthesize(text, language)
            raise RuntimeError("No TTS provider is configured")

        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs.voice_id}/stream"
            headers = {
                "xi-api-key": settings.elevenlabs.api_key,
                "Content-Type": "application/json"
            }
            body = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": settings.elevenlabs.stability,
                    "similarity_boost": settings.elevenlabs.similarity_boost,
                    "style": 0.0,
                    "use_speaker_boost": True,
                    "speed": settings.elevenlabs.speed,
                },
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                return response.content
        except Exception as exc:
            logger.warning("ElevenLabs TTS call failed, using fallback: %s", exc)
            if self.fallback_tts:
                return await self.fallback_tts.synthesize(text, language)
            raise RuntimeError("TTS provider unavailable") from exc
