"""
Data Transfer Objects and Pydantic models for Guardian Dashboard BFF.
Implements: coding-standards §3 (full type hints on dataclass/pydantic models).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel


class LearnerActivitySummary(BaseModel):
    learner_id: UUID
    display_name: str
    age_band: int
    active_relationships_count: int
    last_session_at: datetime
    relationship_health_trend: str = "healthy"  # 'healthy' | 'over_engaged' | 'withdrawn' (PRD §4.4)


class GuardianOverview(BaseModel):
    guardian_id: UUID
    tenant_id: UUID
    learners: list[LearnerActivitySummary]
    consent_status: dict[str, bool]


class IncidentSummary(BaseModel):
    incident_id: str
    learner_id: UUID
    category: str
    created_at: datetime
    sla_deadline: datetime
    is_breached: bool
    acknowledged: bool


class AdminOverview(BaseModel):
    tenant_id: UUID
    total_learners: int
    open_incidents_count: int
    sla_breaches_count: int
    discrepancy_queue_count: int
    recent_incidents: list[IncidentSummary]
