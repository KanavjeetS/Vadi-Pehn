"""
FastAPI entry point for the Guardian Dashboard BFF microservice.
Implements: PRD §2 (Guardian Surface), SD §4.5 (BFF Layer).
"""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import asynccontextmanager
import sys
import os
from uuid import UUID

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api_gateway.auth import enforce_token_scope, require_role
from dashboard_bff.repository import PostgresDashboardRepository
from services.config import settings

from dashboard_bff.models import (
    AdminOverview,
    GuardianOverview,
    IncidentSummary,
    LearnerActivitySummary,
)

dashboard_repo: PostgresDashboardRepository | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global dashboard_repo
    if settings.is_dev:
        yield
        return
    pool = await asyncpg.create_pool(settings.memory_db.dsn, min_size=1, max_size=5)
    dashboard_repo = PostgresDashboardRepository(pool)
    try:
        yield
    finally:
        dashboard_repo = None
        await pool.close()


async def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


app = FastAPI(
    title="Vadi-Pehn Guardian Dashboard BFF",
    description="Backend-For-Frontend serving Guardian surface & Platform Admin triage UI.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "dashboard-bff"}


@app.get("/api/v1/guardian/overview", response_model=GuardianOverview)
async def get_guardian_overview(
    auth: dict[str, object] = Depends(require_role("guardian")),
) -> GuardianOverview:
    """
    Renders RLS-scoped Guardian Dashboard overview.
    Ensures guardian only accesses learners within their tenant.
    """
    tenant_id = UUID(str(auth["tenant_id"]))
    guardian_id = UUID(str(auth["sub"]))
    enforce_token_scope(auth, tenant_id=str(tenant_id), subject_id=str(guardian_id))
    if dashboard_repo is None:
        raise HTTPException(
            status_code=503, detail="dashboard persistence is not ready"
        )
    try:
        learner_rows = await dashboard_repo.learners(tenant_id, guardian_id)
        consent = await _get_json(
            f"{settings.governance.url.rstrip('/')}/internal/v1/governance/consent/summary/{tenant_id}",
            headers={
                "X-Internal-Service-Token": settings.internal_service_token,
                "X-Tenant-ID": str(tenant_id),
            },
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="dashboard dependency unavailable"
        ) from exc

    return GuardianOverview(
        guardian_id=guardian_id,
        tenant_id=tenant_id,
        learners=[
            LearnerActivitySummary(
                learner_id=row["learner_id"],
                display_name=row["display_name"],
                age_band=row["age_band"],
                active_relationships_count=row["active_relationships_count"],
                last_session_at=row["last_session_at"]
                or datetime.fromtimestamp(0, timezone.utc),
                relationship_health_trend=(
                    "healthy"
                    if row["active_relationships_count"] <= 3
                    else "over_engaged"
                ),
            )
            for row in learner_rows
        ],
        consent_status=consent,
    )


@app.get("/api/v1/admin/overview", response_model=AdminOverview)
async def get_admin_overview(
    auth: dict[str, object] = Depends(require_role("admin")),
) -> AdminOverview:
    """
    Renders Platform Admin incident triage overview.
    """
    tenant_id = UUID(str(auth["tenant_id"]))
    if dashboard_repo is None:
        raise HTTPException(
            status_code=503, detail="dashboard persistence is not ready"
        )
    try:
        total_learners = await dashboard_repo.learner_count(tenant_id)
        incidents_data = await _get_json(
            f"{settings.governance.url.rstrip('/')}/internal/v1/governance/incidents/{tenant_id}",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="dashboard dependency unavailable"
        ) from exc
    incidents = incidents_data.get("incidents", [])
    return AdminOverview(
        tenant_id=tenant_id,
        total_learners=total_learners,
        open_incidents_count=sum(
            1 for incident in incidents if not incident.get("acknowledged_at")
        ),
        sla_breaches_count=sum(
            1 for incident in incidents if incident.get("is_breached")
        ),
        discrepancy_queue_count=0,
        recent_incidents=[
            IncidentSummary(
                incident_id=incident["incident_id"],
                learner_id=UUID(incident["learner_id"]),
                category=incident["category"],
                created_at=incident["created_at"],
                sla_deadline=incident["sla_deadline"],
                is_breached=incident["is_breached"],
                acknowledged=bool(incident.get("acknowledged_at")),
            )
            for incident in incidents[:20]
        ],
    )
