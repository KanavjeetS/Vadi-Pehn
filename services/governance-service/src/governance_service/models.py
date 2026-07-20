"""
Data Transfer Objects and Pydantic models for Governance Service.
Implements: coding-standards §3 (full type hints on dataclass/pydantic models).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class ConsentRecord(BaseModel):
    """Granular consent ledger record (PRD §3.2, SD §3.4)."""

    learner_id: UUID
    guardian_id: UUID
    conversation_storage: bool = True
    document_ingestion: bool = True
    voice_recording: bool = True
    career_introductions: bool = True
    updated_at: datetime


class ConsentUpdatePayload(BaseModel):
    """Payload for updating consent settings."""

    conversation_storage: bool | None = None
    document_ingestion: bool | None = None
    voice_recording: bool | None = None
    career_introductions: bool | None = None


class SafetyIncident(BaseModel):
    """Safety incident queue record (PRD §3.3, SD §3.4). Has 7-year legal hold."""

    incident_id: str
    tenant_id: UUID
    learner_id: UUID
    category: str  # e.g., "unsafe_self_harm", "unsafe_abuse_disclosure"
    transcript_excerpt: str
    created_at: datetime
    sla_deadline: datetime  # NOW() + 15 minutes
    acknowledged_at: datetime | None = None
    reviewer_id: str | None = None
    legal_hold: bool = True  # Mandatory 7-year legal hold (PRD §3.3)

    @property
    def is_sla_breached(self) -> bool:
        """Returns True if SLA deadline passed without reviewer acknowledgment."""
        if self.acknowledged_at is not None:
            return False
        return datetime.now(timezone.utc) > self.sla_deadline


class PagingNotification(BaseModel):
    """On-call paging notification DTO for SMS fallback (GUARDRAILS G-003)."""

    incident_id: str
    category: str
    sla_deadline: datetime
    pager_phone: str
    delivered: bool
