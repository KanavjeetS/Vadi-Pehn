"""
Abstract base classes for Voice Gateway components.
Implements: coding-standards §3 (abstract-first pattern).
PRD §6 (Voice-First Experience), SD §4.2 (Voice Gateway).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator
from uuid import UUID


class VADService(ABC):
    """
    Abstract interface for Voice Activity Detection (Silero VAD).
    Responsible for speech boundary and end-of-turn detection.
    """

    @abstractmethod
    async def is_speaking(self, audio_chunk: bytes) -> bool:
        """
        Check if the incoming audio chunk contains active speech.
        """
        ...

    @abstractmethod
    async def detect_speech_end(self, audio_stream: AsyncGenerator[bytes, None]) -> bool:
        """
        Processes an incoming audio stream and returns True when end-of-turn is detected.
        Must respect latency budget (Silero VAD turn detection ≤ 200ms).
        """
        ...


class STTService(ABC):
    """
    Abstract interface for Speech-to-Text translation (Whisper-large-v3).
    Includes safety constraint for no raw audio retention.
    """

    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: str = "en") -> str:
        """
        Transcribe raw audio data into text.
        CRITICAL CHILD-SAFETY REQUIREMENT (PRD §3.4):
        Raw audio data must be processed in-memory and discarded immediately after transcription.
        Must NEVER write raw audio data to disk or persistent databases.
        Must respect latency budget (STT ≤ 500ms).
        """
        ...


class TTSService(ABC):
    """
    Abstract interface for Text-to-Speech synthesis (Kokoro-82M / Piper fallback).
    Supports Hindi and Punjabi with fallback mechanisms.
    """

    @abstractmethod
    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """
        Synthesize text into raw PCM/WAV audio data.
        Must support fallback to Piper if Kokoro fails or lacks multilingual coverage.
        Must respect latency budget (TTS first-chunk ≤ 500ms).
        """
        ...


class LiveKitRoomManager(ABC):
    """
    Abstract interface for LiveKit WebRTC SFU room and participant management.
    Handles signaling handshake, room tokens, and session affinity.
    """

    @abstractmethod
    async def generate_token(self, room_name: str, identity: str) -> str:
        """
        Generate a join token for WebRTC client.
        """
        ...

    @abstractmethod
    async def connect_session(self, session_id: str, token: str) -> Any:
        """
        Establish connection to LiveKit room for a given session.
        Handles reconnection and state recovery.
        """
        ...

    @abstractmethod
    async def stream_audio_to_room(self, room_name: str, audio_data: bytes) -> None:
        """
        Publishes TTS synthesized audio chunks back into the WebRTC SFU room.
        """
        ...
