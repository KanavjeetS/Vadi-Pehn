"""
Data Transfer Objects and Pydantic models for Guardian Dashboard BFF.
Implements: coding-standards §3 (full type hints on dataclass/pydantic models).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class LearnerActivitySummary(BaseModel):
    learner_id: UUID
    display_name: str
    age_band: int
    active_relationships_count: int
    last_session_at: datetime
    relationship_health_trend: str = (
        "healthy"  # 'healthy' | 'over_engaged' | 'withdrawn' (PRD §4.4)
    )


class SessionTrendItem(BaseModel):
    day: str
    minutes: int


class TopicDistributionItem(BaseModel):
    topic: str
    percentage: float
    count: int = 0


class GuardianOverview(BaseModel):
    guardian_id: UUID
    tenant_id: UUID
    learners: list[LearnerActivitySummary]
    active_learners: int = 1
    session_count: int = 0
    weekly_engagement_hours: str = "0h 0m"
    current_streak: str = "0 days"
    most_common_mood: str = "Curious"
    top_growing_skill: str = "World exposure"
    consent_status: dict[str, bool]
    safety_incidents: list[IncidentSummary] = Field(default_factory=list)
    session_trends: list[SessionTrendItem] = Field(default_factory=list)
    topic_distribution: list[TopicDistributionItem] = Field(default_factory=list)


class IncidentSummary(BaseModel):
    incident_id: str
    learner_id: UUID
    category: str
    created_at: datetime
    sla_deadline: datetime
    is_breached: bool
    acknowledged: bool


class ServiceLatencyPercentiles(BaseModel):
    p50: float
    p95: float
    p99: float


class TraceSummaryItem(BaseModel):
    trace_id: str
    session_id: str
    service: str
    latency_ms: float
    status: str
    timestamp: str


class SystemHealthLogItem(BaseModel):
    timestamp: str
    service: str
    level: str
    message: str
    sla_status: str


class AdminOverview(BaseModel):
    tenant_id: UUID
    total_learners: int = 0
    open_incidents_count: int = 0
    sla_breaches_count: int = 0
    discrepancy_queue_count: int = 0
    recent_incidents: list[IncidentSummary] = Field(default_factory=list)
    active_traces: int = 0
    total_sessions: int = 0
    safety_pass_rate: float = 100.0
    service_latencies: dict[str, ServiceLatencyPercentiles] = Field(
        default_factory=dict
    )
    safety_triggers: dict[str, Any] = Field(default_factory=dict)
    sla_metrics: dict[str, Any] = Field(default_factory=dict)
    trace_count_hourly: list[dict[str, Any]] = Field(default_factory=list)
    trace_summaries: list[TraceSummaryItem] = Field(default_factory=list)
    system_health_logs: list[SystemHealthLogItem] = Field(default_factory=list)
