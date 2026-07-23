"""
Empirical test suite for Voice Gateway TTS Fallback Chain.
Tests: ElevenLabs -> Kokoro -> Piper chain under missing key, invalid key, HTTP errors, and offline Piper environments.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "voice-gateway", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from voice_gateway.providers import ElevenLabsTTSService
from voice_gateway.tts import KokoroTTSService, PiperTTSService
from services.config import settings


class TestTTSFallbackChain(unittest.IsolatedAsyncioTestCase):

    async def test_elevenlabs_no_api_key_falls_back_to_kokoro(self):
        """When ElevenLabs API key is absent, it immediately delegates to fallback (Kokoro)."""
        kokoro_mock = AsyncMock()
        kokoro_mock.synthesize.return_value = b"KOKORO_AUDIO"
        
        with patch.object(settings.elevenlabs, "api_key", ""):
            service = ElevenLabsTTSService(fallback_tts=kokoro_mock)
            result = await service.synthesize("Hello world", "en")
            self.assertEqual(result, b"KOKORO_AUDIO")
            kokoro_mock.synthesize.assert_called_once_with("Hello world", "en")

    async def test_elevenlabs_invalid_api_key_401_falls_back_to_kokoro(self):
        """When ElevenLabs returns HTTP 401 (invalid key), it catches exception and falls back to Kokoro."""
        kokoro_mock = AsyncMock()
        kokoro_mock.synthesize.return_value = b"KOKORO_AUDIO"
        
        with patch.object(settings.elevenlabs, "api_key", "invalid_key_123"):
            # Mock httpx.AsyncClient.post to raise HTTPStatusError
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")
            
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                service = ElevenLabsTTSService(fallback_tts=kokoro_mock)
                result = await service.synthesize("Hello world", "en")
                self.assertEqual(result, b"KOKORO_AUDIO")
                kokoro_mock.synthesize.assert_called_once_with("Hello world", "en")

    async def test_full_chain_elevenlabs_fail_kokoro_fail_falls_to_piper(self):
        """When both ElevenLabs and Kokoro fail, execution reaches PiperTTSService."""
        piper_mock = AsyncMock()
        piper_mock.synthesize.return_value = b"PIPER_AUDIO"
        
        kokoro_service = KokoroTTSService(kokoro_url="http://invalid-kokoro-host:9999", fallback_service=piper_mock)
        
        with patch.object(settings.elevenlabs, "api_key", "invalid_key"):
            with patch("httpx.AsyncClient.post", side_effect=Exception("Connection Refused")):
                chain = ElevenLabsTTSService(fallback_tts=kokoro_service)
                result = await chain.synthesize("Hello world", "en")
                self.assertEqual(result, b"PIPER_AUDIO")
                piper_mock.synthesize.assert_called_once_with("Hello world", "en")

    async def test_kokoro_punjabi_routes_directly_to_piper(self):
        """Language 'pa' in Kokoro bypasses Kokoro HTTP request and invokes Piper."""
        piper_mock = AsyncMock()
        piper_mock.synthesize.return_value = b"PIPER_PUNJABI_AUDIO"
        
        kokoro_service = KokoroTTSService(kokoro_url="http://invalid-kokoro-host:9999", fallback_service=piper_mock)
        
        result = await kokoro_service.synthesize("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "pa")
        self.assertEqual(result, b"PIPER_PUNJABI_AUDIO")
        piper_mock.synthesize.assert_called_once_with("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "pa")

    async def test_piper_binary_missing_returns_err_bytes(self):
        """When Piper binary fails or is missing, PiperTTSService returns b'ERR_PIPER_TTS_FAILED' fail-closed byte tag."""
        piper_service = PiperTTSService(piper_path="non_existent_piper_binary")
        result = await piper_service.synthesize("Test", "pa")
        self.assertEqual(result, b"ERR_PIPER_TTS_FAILED")


if __name__ == "__main__":
    unittest.main()
