"""
FastAPI entry point for the Voice Gateway service.
Implements: PRD §6 (Voice-First Experience), SD §4.2 (WebRTC signaling & internal endpoints).
"""
from __future__ import annotations

import sys
import os
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.config import settings
from voice_gateway.models import VoiceTurnRequest, VoiceTurnResponse
from voice_gateway.pipeline import VoiceTurnPipeline
from voice_gateway.vad import MockVADService
from voice_gateway.stt import MockSTTService
from voice_gateway.tts import MockTTSService
from voice_gateway.room_manager import MockRoomManager


app = FastAPI(
    title="Vadi-Pehn Voice Gateway",
    description="WebRTC Voice Gateway managing LiveKit rooms, VAD, STT, TTS, and per-chunk output safety.",
    version="0.1.0",
)

# Global pipeline instance initialized with mock services for dev/tests
pipeline_instance = VoiceTurnPipeline(
    vad_service=MockVADService(),
    stt_service=MockSTTService(),
    tts_service=MockTTSService(),
    room_manager=MockRoomManager(),
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
    await websocket.accept()
    # Connect session in room manager for session affinity and recovery
    await pipeline_instance.room_manager.connect_session(
        session_id=session_id, token="ws_token"
    )
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "ping":
                await websocket.send_json({"action": "pong", "session_id": session_id})
            elif data.get("action") == "voice_turn":
                req = VoiceTurnRequest(
                    session_id=session_id,
                    tenant_id=UUID(data.get("tenant_id", "00000000-0000-0000-0000-000000000001")),
                    learner_id=UUID(data.get("learner_id", "00000000-0000-0000-0000-000000000002")),
                    audio_data_base64=data.get("audio_data_base64"),
                    text_fallback=data.get("text_fallback"),
                    language=data.get("language", "en"),
                )
                res = await pipeline_instance.execute_voice_turn(req)
                await websocket.send_json(res.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
