"""
Data Transfer Objects and Pydantic models for the Panel Service.
Implements: coding-standards §3 (full type hints on dataclass/pydantic models).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class ProfessionalPersona(BaseModel):
    """Represents a domain expert mentor persona in the 8-domain MoE taxonomy."""

    persona_id: str
    code: str  # e.g., "TECH_DEV", "AGRI_BOT", "HEALTH_NURSE"
    title: str
    domain: str  # Agriculture, Technology, Healthcare, Education, Trades, Arts, Business, Government
    profession_taxonomy_code: str
    description: str
    approved_fact_source_ref: str


class PanelRequest(BaseModel):
    """Request payload to trigger a career exploration panel."""

    session_id: str
    tenant_id: UUID
    learner_id: UUID
    query_text: str
    top_interests: list[str] = Field(default_factory=list)
    age_band: int = Field(default=2, ge=1, le=3)


class PanelResponse(BaseModel):
    """Response returned upon running a career exploration panel."""

    panel_id: str
    session_id: str
    status: str  # "success" or "no_match_fallback"
    selected_personas: list[ProfessionalPersona]
    sibling_framing_intro: str | None = None
    synthesized_guidance: str
    persona_audio_base64: str | None = None
    fact_check_passed: bool
    queued_for_curation: bool = False


class OCRDocumentRequest(BaseModel):
    """Request payload for processing an academic document upload (report card, certificate)."""

    document_id: str
    tenant_id: UUID
    learner_id: UUID
    document_type: str  # "report_card", "certificate", "transcript"
    raw_document_base64: str | None = None
    mock_extracted_text: str | None = None


class OCRDocumentResponse(BaseModel):
    """Response returned after processing document OCR and evaluation."""

    document_id: str
    confidence_score: float
    passed_confidence_gate: bool  # True if confidence >= 0.85
    routed_to_discrepancy_queue: bool
    extracted_fields: dict[str, Any]
    pii_redacted: bool


class RelationshipRecord(BaseModel):
    """Mentorship relationship record between a learner and a professional persona."""

    relationship_id: str
    learner_id: UUID
    persona_id: str
    introduced_at: datetime
    last_interaction_at: datetime
    lapsed_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.lapsed_at is None
