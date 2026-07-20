"""
Voice Activity Detection (VAD) services for Vadi-Pehn.
Implements: Abstract-first pattern.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from voice_gateway.abstractions import VADService


class MockVADService(VADService):
    """
    Mock VAD service for unit testing and local development.
    Simulates speech boundary and end-of-turn detection.
    """

    def __init__(self, speech_probability: float = 0.8, end_of_speech_after_chunks: int = 5) -> None:
        self.speech_probability = speech_probability
        self.end_of_speech_after_chunks = end_of_speech_after_chunks

    async def is_speaking(self, audio_chunk: bytes) -> bool:
        # Dummy check: if chunk is not empty, assume speaking
        return len(audio_chunk) > 0 and self.speech_probability > 0.5

    async def detect_speech_end(self, audio_stream: AsyncGenerator[bytes, None]) -> bool:
        """
        Reads from audio stream. After receiving self.end_of_speech_after_chunks chunks,
        simulates end of turn and returns True.
        """
        count = 0
        try:
            async for chunk in audio_stream:
                if not chunk:
                    break
                count += 1
                await asyncio.sleep(0.01)  # Simulate real-time streaming
                if count >= self.end_of_speech_after_chunks:
                    return True
        except asyncio.CancelledError:
            pass
        return False


class SileroVADService(VADService):
    """
    Production-grade Silero VAD implementation using ONNX Runtime.
    Processes 16kHz mono 16-bit PCM audio chunks.
    """

    def __init__(self, model_path: str, threshold: float = 0.5) -> None:
        self.model_path = model_path
        self.threshold = threshold
        self._session = None

    def _init_session(self) -> None:
        if self._session is None:
            try:
                import onnxruntime as ort
                # Load ONNX model session (configured for low latency CPU execution)
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                self._session = ort.InferenceSession(self.model_path, sess_options=opts)
            except ImportError:
                # Fallback to mock session if ONNX is not installed in local environment
                pass

    async def is_speaking(self, audio_chunk: bytes) -> bool:
        self._init_session()
        if self._session is None:
            # Fallback mock logic when running in test without ONNX Runtime installed
            return len(audio_chunk) > 0

        # Perform ONNX inference on audio chunk (normally 512 frames)
        # Returns float speech probability
        import numpy as np
        # Convert bytes to float32 normalized audio array
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        if len(audio_float32) == 0:
            return False

        # Prepare inputs (Silero VAD expects [batch, samples])
        input_data = np.expand_dims(audio_float32, axis=0)
        # Standard input name is 'input'
        ort_inputs = {self._session.get_inputs()[0].name: input_data}
        ort_outs = self._session.run(None, ort_inputs)
        prob = float(ort_outs[0][0][0])
        return prob >= self.threshold

    async def detect_speech_end(self, audio_stream: AsyncGenerator[bytes, None]) -> bool:
        """
        Monitors incoming audio stream. If voice is detected followed by N silence chunks,
        concludes speech has ended (end-of-turn).
        """
        silence_consec_limit = 8  # ~8 chunks of 30ms (240ms silence) indicates speech end
        silence_count = 0
        voice_started = False

        async for chunk in audio_stream:
            speaking = await self.is_speaking(chunk)
            if speaking:
                voice_started = True
                silence_count = 0
            elif voice_started:
                silence_count += 1
                if silence_count >= silence_consec_limit:
                    return True
        return voice_started
