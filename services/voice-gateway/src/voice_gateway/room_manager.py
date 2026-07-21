"""
LiveKit SFU room management services for Vadi-Pehn.
Implements: Abstract-first pattern.
Handles WebRTC signaling handshake, join tokens, and room connections.
"""

from __future__ import annotations

import uuid
from typing import Any
from voice_gateway.abstractions import LiveKitRoomManager


class MockRoomManager(LiveKitRoomManager):
    """
    Mock LiveKit Room Manager for testing and local dev.
    Tracks active sessions, room states, and stream publishing without needing a live SFU server.
    """

    def __init__(self) -> None:
        self.active_rooms: dict[str, set[str]] = {}
        self.published_chunks: dict[str, list[bytes]] = {}
        self.session_states: dict[str, dict[str, Any]] = {}

    async def generate_token(self, room_name: str, identity: str) -> str:
        """Generates a mock JWT join token."""
        return f"mock_token_{room_name}_{identity}_{uuid.uuid4().hex[:8]}"

    async def connect_session(self, session_id: str, token: str) -> dict[str, Any]:
        """
        Simulates connecting to a LiveKit room.
        Maintains session affinity for reconnects (SD §7 failure modes).
        """
        if session_id not in self.session_states:
            self.session_states[session_id] = {
                "session_id": session_id,
                "token": token,
                "connected": True,
                "reconnect_count": 0,
            }
        else:
            self.session_states[session_id]["reconnect_count"] += 1
            self.session_states[session_id]["connected"] = True

        room_name = f"room_{session_id}"
        if room_name not in self.active_rooms:
            self.active_rooms[room_name] = set()
        self.active_rooms[room_name].add(session_id)

        return self.session_states[session_id]

    async def stream_audio_to_room(self, room_name: str, audio_data: bytes) -> None:
        """
        Simulates publishing audio bytes into the LiveKit WebRTC room data channel.
        """
        if room_name not in self.published_chunks:
            self.published_chunks[room_name] = []
        self.published_chunks[room_name].append(audio_data)


class ProductionLiveKitRoomManager(LiveKitRoomManager):
    """
    Production LiveKit API client wrapper.
    Generates real LiveKit JWT access tokens and communicates with the LiveKit SFU server.
    """

    def __init__(self, livekit_url: str, api_key: str, api_secret: str) -> None:
        self.livekit_url = livekit_url
        self.api_key = api_key
        self.api_secret = api_secret
        self._rooms: dict[str, Any] = {}
        self._sources: dict[str, Any] = {}

    async def generate_token(self, room_name: str, identity: str) -> str:
        try:
            from livekit import api

            return (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(identity)
                .with_grants(
                    api.VideoGrants(
                        room_join=True,
                        room=room_name,
                        can_publish=True,
                        can_subscribe=True,
                    )
                )
                .to_jwt()
            )
        except ImportError as exc:
            raise RuntimeError(
                "livekit-api is required for production room tokens"
            ) from exc

    async def connect_session(self, session_id: str, token: str) -> dict[str, Any]:
        """Connect a server-side publisher to the LiveKit room."""
        try:
            from livekit import rtc

            room = rtc.Room()
            await room.connect(self.livekit_url, token)
            source = rtc.AudioSource(48000, 1)
            track = rtc.LocalAudioTrack.create_audio_track("vadi-response", source)
            await room.local_participant.publish_track(track)
            self._rooms[session_id] = room
            self._sources[session_id] = source
            return {
                "session_id": session_id,
                "status": "connected",
                "url": self.livekit_url,
            }
        except ImportError as exc:
            raise RuntimeError(
                "livekit-rtc is required for production audio publishing"
            ) from exc

    async def stream_audio_to_room(self, room_name: str, audio_data: bytes) -> None:
        """Publish a WAV/PCM chunk to the connected server publisher."""
        session_id = room_name.removeprefix("room_")
        source = self._sources.get(session_id)
        if source is None:
            raise RuntimeError("LiveKit session is not connected")
        pcm, sample_rate = _decode_audio_chunk(audio_data)
        from livekit import rtc

        await source.capture_frame(
            rtc.AudioFrame(
                data=pcm,
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=len(pcm) // 2,
            )
        )


def _decode_audio_chunk(audio_data: bytes) -> tuple[bytes, int]:
    """Decode TTS WAV output to signed 16-bit mono PCM for LiveKit."""
    import io
    import wave

    try:
        with wave.open(io.BytesIO(audio_data), "rb") as wav:
            if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
                raise ValueError("LiveKit publisher requires mono 16-bit PCM")
            return wav.readframes(wav.getnframes()), wav.getframerate()
    except (wave.Error, ValueError):
        return audio_data, 48000
