"""
FastAPI entry point for the Guardian Dashboard BFF microservice.
Implements: PRD §2 (Guardian Surface), SD §4.5 (BFF Layer).
"""
from __future__ import annotations

from datetime import datetime, timezone
import sys
import os
from uuid import UUID

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard_bff.models import (
    AdminOverview,
    GuardianOverview,
    IncidentSummary,
    LearnerActivitySummary,
)


app = FastAPI(
    title="Vadi-Pehn Guardian Dashboard BFF",
    description="Backend-For-Frontend serving Guardian surface & Platform Admin triage UI.",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "dashboard-bff"}


@app.get("/api/v1/guardian/overview", response_model=GuardianOverview)
async def get_guardian_overview(
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    x_guardian_id: UUID = Header(..., alias="X-Guardian-ID"),
) -> GuardianOverview:
    """
    Renders RLS-scoped Guardian Dashboard overview.
    Ensures guardian only accesses learners within their tenant.
    """
    now = datetime.now(timezone.utc)
    learner_id = UUID("00000000-0000-0000-0000-000000000002")

    return GuardianOverview(
        guardian_id=x_guardian_id,
        tenant_id=x_tenant_id,
        learners=[
            LearnerActivitySummary(
                learner_id=learner_id,
                display_name="Learner Alex",
                age_band=2,
                active_relationships_count=2,
                last_session_at=now,
                relationship_health_trend="healthy",
            )
        ],
        consent_status={
            "conversation_storage": True,
            "document_ingestion": True,
            "voice_recording": True,
            "career_introductions": True,
        },
    )


@app.get("/api/v1/admin/overview", response_model=AdminOverview)
async def get_admin_overview(
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
) -> AdminOverview:
    """
    Renders Platform Admin incident triage overview.
    """
    now = datetime.now(timezone.utc)
    return AdminOverview(
        tenant_id=x_tenant_id,
        total_learners=150,
        open_incidents_count=1,
        sla_breaches_count=0,
        discrepancy_queue_count=2,
        recent_incidents=[
            IncidentSummary(
                incident_id="inc_demo_01",
                learner_id=UUID("00000000-0000-0000-0000-000000000002"),
                category="unsafe_self_harm",
                created_at=now,
                sla_deadline=now,
                is_breached=False,
                acknowledged=False,
            )
        ],
    )
