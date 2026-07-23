"""
FastAPI entry point for the Guardian Dashboard BFF microservice.
Implements: PRD §2 (Guardian Surface), SD §4.5 (BFF Layer).
"""

from __future__ import annotations

import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api_gateway.auth import enforce_token_scope, require_role
from dashboard_bff.models import (
    AdminOverview,
    GuardianOverview,
    IncidentSummary,
    LearnerActivitySummary,
)
from dashboard_bff.repository import (
    InMemoryDashboardRepository,
    PostgresDashboardRepository,
)
from services.config import settings
from services.logging_config import configure_logging

configure_logging("dashboard-bff")

dashboard_repo: PostgresDashboardRepository | InMemoryDashboardRepository | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global dashboard_repo
    if settings.is_dev:
        dashboard_repo = InMemoryDashboardRepository()
        try:
            yield
        finally:
            dashboard_repo = None
        return

    pool = await asyncpg.create_pool(settings.memory_db.dsn, min_size=1, max_size=5)
    dashboard_repo = PostgresDashboardRepository(pool)
    try:
        yield
    finally:
        dashboard_repo = None
        await pool.close()


async def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        if settings.is_dev:
            if "consent/summary" in url:
                return {
                    "conversation_storage": True,
                    "document_ingestion": True,
                    "voice_recording": True,
                    "career_introductions": True,
                }
            if "incidents" in url:
                return {"incidents": []}
        raise


async def _post_json(
    url: str, json_data: dict, *, headers: dict[str, str] | None = None
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(url, json=json_data, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        if settings.is_dev:
            return {
                "incident_id": "inc_dev_ack",
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }
        raise


from dashboard_bff.admin_observability import router as admin_observability_router  # noqa: E402

app = FastAPI(
    title="Vadi-Pehn Guardian Dashboard BFF",
    description="Backend-For-Frontend serving Guardian surface & Platform Admin triage UI.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(admin_observability_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


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
        learner_ids = [row["learner_id"] for row in learner_rows if "learner_id" in row]

        session_count = await dashboard_repo.session_count(tenant_id, learner_ids)
        streak_str = await dashboard_repo.learner_streak(tenant_id, guardian_id)
        weekly_engagement_str = await dashboard_repo.weekly_engagement(tenant_id, guardian_id)
        top_skill = await dashboard_repo.top_growing_skill(tenant_id, learner_ids)

        consent = await _get_json(
            f"{settings.governance.url.rstrip('/')}/internal/v1/governance/consent/summary/{tenant_id}",
            headers={
                "X-Internal-Service-Token": settings.internal_service_token,
                "X-Tenant-ID": str(tenant_id),
            },
        )
        try:
            incidents_data = await _get_json(
                f"{settings.governance.url.rstrip('/')}/internal/v1/governance/incidents/{tenant_id}",
                headers={"X-Internal-Service-Token": settings.internal_service_token},
            )
        except Exception:
            incidents_data = {"incidents": []}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="dashboard dependency unavailable"
        ) from exc

    raw_incidents = incidents_data.get("incidents", [])
    incidents = [
        IncidentSummary(
            incident_id=inc["incident_id"],
            learner_id=UUID(inc["learner_id"]),
            category=inc.get("category") or inc.get("severity") or "general",
            created_at=inc["created_at"],
            sla_deadline=inc["sla_deadline"],
            is_breached=inc.get("is_breached", False),
            acknowledged=bool(inc.get("acknowledged_at")),
        )
        for inc in raw_incidents
    ]

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
        active_learners=len(learner_rows),
        session_count=session_count,
        weekly_engagement_hours=weekly_engagement_str,
        current_streak=streak_str,
        most_common_mood="Curious",
        top_growing_skill=top_skill,
        consent_status=consent,
        safety_incidents=incidents,
    )


@app.post("/api/v1/guardian/incident/{incident_id}/acknowledge")
async def acknowledge_guardian_incident(
    incident_id: str,
    auth: dict[str, object] = Depends(require_role("guardian")),
) -> dict[str, object]:
    tenant_id = UUID(str(auth["tenant_id"]))
    guardian_id = UUID(str(auth["sub"]))
    enforce_token_scope(auth, tenant_id=str(tenant_id), subject_id=str(guardian_id))

    try:
        res = await _post_json(
            f"{settings.governance.url.rstrip('/')}/internal/v1/governance/incident/{incident_id}/acknowledge",
            {"reviewer_id": str(guardian_id)},
            headers={"X-Internal-Service-Token": settings.internal_service_token},
        )
        return {"status": "acknowledged", "incident": res}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="governance service unavailable"
        ) from exc


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
        discrepancy_count = await dashboard_repo.discrepancy_count(tenant_id)
        total_sessions = await dashboard_repo.total_sessions_count(tenant_id)

        incidents_data = await _get_json(
            f"{settings.governance.url.rstrip('/')}/internal/v1/governance/incidents/{tenant_id}",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="dashboard dependency unavailable"
        ) from exc
    incidents = incidents_data.get("incidents", [])
    open_incidents = sum(1 for incident in incidents if not incident.get("acknowledged_at"))
    sla_breaches = sum(1 for incident in incidents if incident.get("is_breached"))
    total_incidents = len(incidents)
    safety_pass_rate = (
        100.0
        if total_incidents == 0
        else max(0.0, round(100.0 - (total_incidents * 2.0), 2))
    )

    return AdminOverview(
        tenant_id=tenant_id,
        total_learners=total_learners,
        open_incidents_count=open_incidents,
        sla_breaches_count=sla_breaches,
        discrepancy_queue_count=discrepancy_count,
        total_sessions=total_sessions,
        active_traces=total_sessions,
        safety_pass_rate=safety_pass_rate,
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
