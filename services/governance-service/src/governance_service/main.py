"""
FastAPI entry point for the Governance Service.
Implements: PRD §3 (Consent Ledger & Incident Management), SD §3.4.
"""

from __future__ import annotations

import sys
import os
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from governance_service.consent_ledger import ConsentLedger, PostgresConsentLedger
from governance_service.incident_queue import IncidentEscalationQueue
from governance_service.models import (
    ConsentRecord,
    ConsentUpdatePayload,
    SafetyIncident,
)
from services.config import require_internal_service_token, settings

ledger = ConsentLedger()
queue = IncidentEscalationQueue(sms_webhook_url=settings.governance.sms_webhook_url)
governance_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global governance_pool, ledger, queue
    governance_pool = await asyncpg.create_pool(
        settings.governance_db.dsn, min_size=1, max_size=5
    )
    ledger = PostgresConsentLedger(governance_pool)
    queue = IncidentEscalationQueue(
        sms_webhook_url=settings.governance.sms_webhook_url, pool=governance_pool
    )
    try:
        yield
    finally:
        await governance_pool.close()
        governance_pool = None


app = FastAPI(
    title="Vadi-Pehn Governance Service",
    description="Governance Service managing Consent Ledger, Safety Incident Escalations, and Retentions.",
    version="0.2.0",
    lifespan=lifespan,
)


class IncidentCreateRequest(BaseModel):
    learner_id: UUID
    tenant_id: UUID
    category: str
    transcript_excerpt: str


class IncidentAcknowledgeRequest(BaseModel):
    reviewer_id: str


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "governance-service"}


@app.get("/internal/v1/governance/consent/{learner_id}", response_model=ConsentRecord)
async def get_consent(
    learner_id: UUID,
    x_tenant_id: UUID = Header(...),
    x_internal_service_token: str = Header(default=""),
) -> ConsentRecord:
    require_internal_service_token(x_internal_service_token)
    if not isinstance(ledger, PostgresConsentLedger):
        raise HTTPException(
            status_code=503, detail="governance persistence is not ready"
        )
    return await ledger.get_consent_record(learner_id=learner_id, tenant_id=x_tenant_id)


@app.get("/internal/v1/governance/consent/summary/{tenant_id}")
async def consent_summary(
    tenant_id: UUID, x_internal_service_token: str = Header(default="")
) -> dict[str, bool]:
    require_internal_service_token(x_internal_service_token)
    if not isinstance(ledger, PostgresConsentLedger):
        raise HTTPException(
            status_code=503, detail="governance persistence is not ready"
        )
    return await ledger.summary(tenant_id=tenant_id)


@app.post("/internal/v1/governance/consent/{learner_id}", response_model=ConsentRecord)
async def update_consent(
    learner_id: UUID,
    payload: ConsentUpdatePayload,
    x_tenant_id: UUID = Header(...),
    x_guardian_id: UUID = Header(...),
    x_internal_service_token: str = Header(default=""),
) -> ConsentRecord:
    require_internal_service_token(x_internal_service_token)
    if not isinstance(ledger, PostgresConsentLedger):
        raise HTTPException(
            status_code=503, detail="governance persistence is not ready"
        )
    return await ledger.update_consent(
        learner_id=learner_id,
        payload=payload,
        tenant_id=x_tenant_id,
        guardian_id=x_guardian_id,
    )


@app.post("/internal/v1/governance/incident", response_model=SafetyIncident)
async def create_incident(
    request: IncidentCreateRequest, x_internal_service_token: str = Header(default="")
) -> SafetyIncident:
    require_internal_service_token(x_internal_service_token)
    return await queue.create_incident(
        learner_id=request.learner_id,
        tenant_id=request.tenant_id,
        category=request.category,
        transcript_excerpt=request.transcript_excerpt,
    )


@app.get("/internal/v1/governance/incidents/{tenant_id}")
async def list_incidents(
    tenant_id: UUID, x_internal_service_token: str = Header(default="")
) -> dict[str, list[dict]]:
    require_internal_service_token(x_internal_service_token)
    if governance_pool is None:
        raise HTTPException(
            status_code=503, detail="governance persistence is not ready"
        )
    incidents = await queue.list_incidents(tenant_id=tenant_id)
    return {
        "incidents": [
            incident.model_dump(mode="json") | {"is_breached": incident.is_sla_breached}
            for incident in incidents
        ]
    }


@app.post(
    "/internal/v1/governance/incident/{incident_id}/acknowledge",
    response_model=SafetyIncident,
)
async def acknowledge_incident(
    incident_id: str,
    request: IncidentAcknowledgeRequest,
    x_internal_service_token: str = Header(default=""),
) -> SafetyIncident:
    require_internal_service_token(x_internal_service_token)
    try:
        return await queue.acknowledge_incident(
            incident_id=incident_id, reviewer_id=request.reviewer_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")
