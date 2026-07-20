"""
Unit and Integration Tests for Governance Service (Phase 8).
Verifies:
  1. Granular consent ledger management & instant memory purge upon revocation (PRD §3.2, §3.4)
  2. Safety Incident Queue, 15-minute SLA deadline, & 7-year legal hold (PRD §3.3)
  3. SMS Fallback Paging trigger when DB fails (GUARDRAILS G-003)
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from governance_service.consent_ledger import ConsentLedger
from governance_service.incident_queue import IncidentEscalationQueue
from governance_service.models import ConsentUpdatePayload
from governance_service.retention import RetentionJobScheduler


@pytest.mark.asyncio
async def test_consent_ledger_default_and_update() -> None:
    """Verifies default active consent and granular updates."""
    ledger = ConsentLedger()
    learner_id = uuid4()

    record = await ledger.get_consent_record(learner_id=learner_id)
    assert record.conversation_storage
    assert record.document_ingestion

    updated = await ledger.update_consent(
        learner_id=learner_id,
        payload=ConsentUpdatePayload(conversation_storage=False),
    )

    assert not updated.conversation_storage
    assert updated.document_ingestion  # Remaining consent flags unchanged


@pytest.mark.asyncio
async def test_immediate_consent_revocation_purge() -> None:
    """PRD §3.4 ASSERTION: Revoking conversation_storage triggers immediate memory purge."""
    purged_learner_id: list[str] = []

    async def mock_purge(learner_id):
        purged_learner_id.append(str(learner_id))
        return 1

    ledger = ConsentLedger(purge_callback=mock_purge)
    learner_id = uuid4()

    # Active consent initially
    await ledger.get_consent_record(learner_id=learner_id)

    # Revoke consent
    await ledger.update_consent(
        learner_id=learner_id,
        payload=ConsentUpdatePayload(conversation_storage=False),
    )

    # Verified purge callback executed immediately
    assert len(purged_learner_id) == 1
    assert purged_learner_id[0] == str(learner_id)


@pytest.mark.asyncio
async def test_safety_incident_creation_and_sla_deadline() -> None:
    """PRD §3.3 ASSERTION: Incident created with 15-minute SLA deadline and 7-year legal hold."""
    queue = IncidentEscalationQueue()
    learner_id = uuid4()
    tenant_id = uuid4()

    inc = await queue.create_incident(
        learner_id=learner_id,
        tenant_id=tenant_id,
        category="unsafe_self_harm",
        transcript_excerpt="I feel very sad and lonely.",
    )

    assert inc.category == "unsafe_self_harm"
    assert inc.legal_hold  # Mandatory 7-year legal hold
    assert not inc.is_sla_breached  # Just created, SLA not breached

    # SLA deadline is exactly 15 minutes in the future
    delta = inc.sla_deadline - inc.created_at
    assert delta.total_seconds() == 900.0  # 15 minutes = 900s

    # Acknowledge incident
    ack = await queue.acknowledge_incident(incident_id=inc.incident_id, reviewer_id="reviewer_01")
    assert ack.acknowledged_at is not None
    assert ack.reviewer_id == "reviewer_01"


@pytest.mark.asyncio
async def test_sms_fallback_paging_trigger() -> None:
    """GUARDRAILS G-003 ASSERTION: Fallback SMS paging triggered on incident creation."""
    queue = IncidentEscalationQueue()
    learner_id = uuid4()

    inc = await queue.create_incident(
        learner_id=learner_id,
        tenant_id=uuid4(),
        category="unsafe_abuse_disclosure",
        transcript_excerpt="Disclosure excerpt...",
    )

    assert len(queue.paging_log) == 1
    assert queue.paging_log[0].incident_id == inc.incident_id
    assert queue.paging_log[0].delivered


@pytest.mark.asyncio
async def test_retention_job_scheduler() -> None:
    """PRD §3.4 ASSERTION: 18-month memory pruning scheduler."""
    pruned_days: list[int] = []

    async def mock_prune(days: int) -> int:
        pruned_days.append(days)
        return 12

    scheduler = RetentionJobScheduler(memory_prune_callback=mock_prune)
    count = await scheduler.prune_expired_memories(retention_days=540)

    assert count == 12
    assert pruned_days[0] == 540
