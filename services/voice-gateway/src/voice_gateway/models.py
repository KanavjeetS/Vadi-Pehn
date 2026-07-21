"""
Data transfer objects and models for the Voice Gateway.
Implements: coding-standards §3 (full type hints on dataclass/pydantic models).
"""

from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field


class LatencyReport(BaseModel):
    """
    Sub-3700ms Latency Budget constraints (PRD §6.2).
    Tracks timing per component to assert performance constraints.
    """

    vad_ms: float = 0.0
    stt_ms: float = 0.0
    safety_input_ms: float = 0.0
    llm_first_chunk_ms: float = 0.0
    safety_output_per_chunk_ms: float = 0.0
    tts_first_chunk_ms: float = 0.0
    total_e2e_ms: float = 0.0

    def is_within_budget(self) -> bool:
        """Total E2E p95 must be <= 3700ms."""
        return self.total_e2e_ms <= 3700.0


class VoiceTurnRequest(BaseModel):
    """Payload representing a client voice turn request (for simulation/WebSockets)."""

    session_id: str
    tenant_id: UUID
    learner_id: UUID
    age_band: int = Field(default=2, ge=1, le=3)
    audio_data_base64: str | None = None
    text_fallback: str | None = (
        None  # in case client network doesn't support streaming audio
    )
    language: str = "en"


class VoiceTurnResponse(BaseModel):
    """Response returned upon completing a voice turn."""

    session_id: str
    turn_id: str
    transcript_text: str
    reply_text: str
    safety_verdict: str
    latency_report: LatencyReport
    audio_response_base64: str | None = None
