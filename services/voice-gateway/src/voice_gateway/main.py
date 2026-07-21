"""
FastAPI entry point for the Voice Gateway service.
Implements: PRD §6 (Voice-First Experience), SD §4.2 (WebRTC signaling & internal endpoints).
"""

from __future__ import annotations

import asyncio
import sys
import os
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "safety-proxy", "src")
)

from services.config import settings
from safety_proxy.client import NeMoSafetyClient
from voice_gateway.models import VoiceTurnRequest, VoiceTurnResponse
from voice_gateway.pipeline import VoiceTurnPipeline
from voice_gateway.vad import MockVADService, SileroVADService
from voice_gateway.stt import MockSTTService, WhisperSTTService
from voice_gateway.tts import KokoroTTSService, MockTTSService, PiperTTSService
from voice_gateway.room_manager import MockRoomManager, ProductionLiveKitRoomManager
from voice_gateway.orchestration_client import RemoteOrchestrationClient

app = FastAPI(
    title="Vadi-Pehn Voice Gateway",
    description="WebRTC Voice Gateway managing LiveKit rooms, VAD, STT, TTS, and per-chunk output safety.",
    version="0.1.0",
)

from voice_gateway.providers import GroqSTTService, ElevenLabsTTSService, LiveKitTokenService

# Development stays hermetic; pilot/production uses the configured network services.
if settings.is_dev:
    _base_stt = MockSTTService()
    _base_tts = MockTTSService()
    _vad_service = MockVADService()
    _room_manager = MockRoomManager()
else:
    _vad_service = SileroVADService(settings.voice.vad_model_path)
    _base_stt = WhisperSTTService(
        settings.voice.whisper_url, settings.voice.whisper_model
    )
    _base_tts = KokoroTTSService(
        settings.voice.kokoro_url,
        fallback_service=PiperTTSService(settings.voice.piper_path),
    )
    _room_manager = ProductionLiveKitRoomManager(
        settings.livekit.url,
        settings.livekit.api_key,
        settings.livekit.api_secret,
    )

# Wrap with ultra-low latency Groq and ElevenLabs providers (with automatic fallbacks)
_stt_service = GroqSTTService(fallback_stt=_base_stt)
_tts_service = ElevenLabsTTSService(fallback_tts=_base_tts)

pipeline_instance = VoiceTurnPipeline(
    vad_service=_vad_service,
    stt_service=_stt_service,
    tts_service=_tts_service,
    room_manager=_room_manager,
    safety_client=NeMoSafetyClient(),
    orchestration_graph=None if settings.is_dev else RemoteOrchestrationClient(),
)


class ConnectTokenRequest(BaseModel):
    session_id: str
    identity: str


class ConnectTokenResponse(BaseModel):
    session_id: str
    token: str
    livekit_url: str


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "voice-gateway"}


@app.post("/internal/v1/voice/token", response_model=ConnectTokenResponse)
async def generate_join_token(request: ConnectTokenRequest) -> ConnectTokenResponse:
    """
    Generates WebRTC join token for client connection to LiveKit SFU (SD §4.2).
    """
    token = await pipeline_instance.room_manager.generate_token(
        room_name=f"room_{request.session_id}", identity=request.identity
    )
    return ConnectTokenResponse(
        session_id=request.session_id,
        token=token,
        livekit_url=settings.livekit.url,
    )


@app.post("/internal/v1/voice/turn", response_model=VoiceTurnResponse)
async def process_voice_turn(request: VoiceTurnRequest) -> VoiceTurnResponse:
    """
    Execute a voice turn: VAD -> STT -> Safety Check Input -> LLM -> Per-Chunk Output Safety -> TTS.
    """
    try:
        return await pipeline_instance.execute_voice_turn(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/v1/voice/connect")
async def websocket_voice_connect(websocket: WebSocket, session_id: str) -> None:
    """
    WebRTC signaling & session connection endpoint (SD §4.2).
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="LiveKit token required")
        return
    await websocket.accept()
    # Connect session in room manager for session affinity and recovery
    await pipeline_instance.room_manager.connect_session(
        session_id=session_id, token=token
    )
    turn_task: asyncio.Task[VoiceTurnResponse] | None = None
    try:
        while True:
            receive_task = asyncio.create_task(websocket.receive_json())
            wait_set: set[asyncio.Task[object]] = {receive_task}
            if turn_task is not None:
                wait_set.add(turn_task)  # type: ignore[arg-type]
            done, _ = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)
            if turn_task is not None and turn_task in done:
                result = turn_task.result()
                await websocket.send_json(result.model_dump(mode="json"))
                turn_task = None
                if receive_task not in done:
                    receive_task.cancel()
                    await asyncio.gather(receive_task, return_exceptions=True)
                continue
            data = receive_task.result()
            if data.get("action") == "ping":
                await websocket.send_json({"action": "pong", "session_id": session_id})
            elif data.get("action") == "barge_in":
                pipeline_instance.trigger_barge_in(session_id)
                if turn_task is not None:
                    turn_task.cancel()
                    await asyncio.gather(turn_task, return_exceptions=True)
                    turn_task = None
                await websocket.send_json(
                    {"action": "interrupted", "session_id": session_id}
                )
            elif data.get("action") == "voice_turn":
                if turn_task is not None:
                    await websocket.send_json({"error": "voice turn already active"})
                    continue
                tenant_id = data.get("tenant_id")
                learner_id = data.get("learner_id")
                if not tenant_id or not learner_id:
                    await websocket.send_json(
                        {"error": "tenant_id and learner_id required"}
                    )
                    continue
                req = VoiceTurnRequest(
                    session_id=session_id,
                    tenant_id=UUID(tenant_id),
                    learner_id=UUID(learner_id),
                    audio_data_base64=data.get("audio_data_base64"),
                    text_fallback=data.get("text_fallback"),
                    language=data.get("language", "en"),
                )
                turn_task = asyncio.create_task(
                    pipeline_instance.execute_voice_turn(req)
                )
    except WebSocketDisconnect:
        if turn_task is not None:
            turn_task.cancel()
            await asyncio.gather(turn_task, return_exceptions=True)
