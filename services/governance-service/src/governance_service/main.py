"""
FastAPI entry point for the Governance Service.
Implements: PRD §3 (Consent Ledger & Incident Management), SD §3.4.
"""
from __future__ import annotations

import sys
import os
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from governance_service.consent_ledger import ConsentLedger
from governance_service.incident_queue import IncidentEscalationQueue
from governance_service.models import ConsentRecord, ConsentUpdatePayload, SafetyIncident


app = FastAPI(
    title="Vadi-Pehn Governance Service",
    description="Governance Service managing Consent Ledger, Safety Incident Escalations, and Retentions.",
    version="0.1.0",
)

ledger = ConsentLedger()
queue = IncidentEscalationQueue()


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
async def get_consent(learner_id: UUID) -> ConsentRecord:
    return await ledger.get_consent_record(learner_id=learner_id)


@app.post("/internal/v1/governance/consent/{learner_id}", response_model=ConsentRecord)
async def update_consent(learner_id: UUID, payload: ConsentUpdatePayload) -> ConsentRecord:
    return await ledger.update_consent(learner_id=learner_id, payload=payload)


@app.post("/internal/v1/governance/incident", response_model=SafetyIncident)
async def create_incident(request: IncidentCreateRequest) -> SafetyIncident:
    return await queue.create_incident(
        learner_id=request.learner_id,
        tenant_id=request.tenant_id,
        category=request.category,
        transcript_excerpt=request.transcript_excerpt,
    )


@app.post("/internal/v1/governance/incident/{incident_id}/acknowledge", response_model=SafetyIncident)
async def acknowledge_incident(incident_id: str, request: IncidentAcknowledgeRequest) -> SafetyIncident:
    try:
        return await queue.acknowledge_incident(incident_id=incident_id, reviewer_id=request.reviewer_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")
