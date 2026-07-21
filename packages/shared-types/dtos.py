"""
Shared DTO Models matching vadi-sis frontend & backend service interfaces.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class LearnerProfileDTO(BaseModel):
    learner_id: UUID
    tenant_id: UUID
    display_name: str
    age: int
    preferred_language: str = "en"
    interests: List[str] = Field(default_factory=list)


class ConversationTurnDTO(BaseModel):
    session_id: str
    tenant_id: UUID
    learner_id: UUID
    user_message: str
    agent_response: Optional[str] = None
    agent_persona: str = "sibling"  # 'sibling', 'professional', 'curator'
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceStreamChunkDTO(BaseModel):
    session_id: str
    sentence_chunk: str
    audio_base64: Optional[str] = None
    is_final: bool = False
    latency_ms: float = 0.0


class DocumentUploadRequestDTO(BaseModel):
    tenant_id: UUID
    learner_id: UUID
    filename: str
    file_type: str  # 'report_card', 'certificate', 'essay'
