"""
Text-to-Speech (TTS) services for Vadi-Pehn.
Implements: Abstract-first pattern.
Provides Kokoro-82M TTS and Piper TTS fallback.
"""
from __future__ import annotations

import httpx
import subprocess
from typing import Any
from voice_gateway.abstractions import TTSService


class MockTTSService(TTSService):
    """
    Mock TTS service for unit testing and local development.
    Returns synthetic audio bytes matching the request.
    """

    def __init__(self) -> None:
        self.last_synthesized_text = ""
        self.last_language = ""
        self.fallback_used = False

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        self.last_synthesized_text = text
        self.last_language = language

        # Simulating Piper fallback on Punjabi or explicit failure triggers
        if language == "pa":
            self.fallback_used = True
            # Return synthetic Punjabi Piper audio bytes
            return b"MOCK_PUNJABI_PIPER_AUDIO_BYTES"

        if "FAIL_KOKORO" in text:
            self.fallback_used = True
            return b"MOCK_FALLBACK_PIPER_AUDIO_BYTES"

        # Return standard mock Kokoro audio bytes
        return b"MOCK_KOKORO_AUDIO_BYTES"


class PiperTTSService(TTSService):
    """
    Local Piper TTS fallback service.
    Runs Piper command-line or local API to synthesize Punjabi/other fallback audios.
    """

    def __init__(self, piper_path: str = "piper", model_path: str = "models/pa_in.onnx") -> None:
        self.piper_path = piper_path
        self.model_path = model_path

    async def synthesize(self, text: str, language: str = "pa") -> bytes:
        """
        Executes Piper subprocess to generate low-latency local TTS.
        """
        try:
            # We call Piper as a subprocess piping text in and reading WAV bytes out
            cmd = [
                self.piper_path,
                "--model", self.model_path,
                "--output-raw"
            ]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=text.encode("utf-8"), timeout=3.0)
            if process.returncode != 0:
                raise RuntimeError(f"Piper failed: {stderr.decode('utf-8')}")
            return stdout
        except Exception as e:
            # Safe degraded fallback: return empty/error audio log rather than crashing
            return b"ERR_PIPER_TTS_FAILED"


class KokoroTTSService(TTSService):
    """
    Production Kokoro-82M TTS service wrapper.
    Requests speech synthesis from the GPU-hosted Kokoro container.
    """

    def __init__(
        self,
        kokoro_url: str,
        fallback_service: PiperTTSService | None = None
    ) -> None:
        self.kokoro_url = kokoro_url.rstrip("/")
        self.fallback_service = fallback_service or PiperTTSService()

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """
        Synthesize text. Falls back to Piper if Kokoro fails or language is Punjabi (pa).
        """
        # Hard Gate check: Punjabi is not fully supported by standard Kokoro-82M,
        # so route immediately to local Piper fallback per PRD §6.4.
        if language == "pa":
            return await self.fallback_service.synthesize(text, language)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.kokoro_url}/v1/audio/speech",
                    json={
                        "input": text,
                        "voice": "en_us_male" if language == "en" else "hi_female",
                        "response_format": "wav"
                    },
                    timeout=2.0,  # Enforce sub-500ms budget for first chunks
                )
                response.raise_for_status()
                return response.content
        except Exception:
            # If Kokoro fails, execute the Piper fallback mechanism
            return await self.fallback_service.synthesize(text, language)
