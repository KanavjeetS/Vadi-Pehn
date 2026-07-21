"""
Abstract base classes for the Governance Service.
Implements: coding-standards §3 (abstract-first pattern).
PRD §3 (Consent & Governance), SD §3.4 (Governance DB).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from governance_service.models import (
    ConsentRecord,
    ConsentUpdatePayload,
    SafetyIncident,
)


class ConsentLedgerEngine(ABC):
    """
    Abstract interface for Consent Ledger operations.
    PRD §3.2: Granular consent (conversational data, documents, voice, career panel).
    Immediate deletion trigger upon withdrawal.
    """

    @abstractmethod
    async def get_consent_record(self, *, learner_id: UUID) -> ConsentRecord:
        """Fetch current granular consent settings for a learner."""
        ...

    @abstractmethod
    async def update_consent(
        self, *, learner_id: UUID, payload: ConsentUpdatePayload
    ) -> ConsentRecord:
        """Update consent settings. Revoking consent triggers immediate data deletion."""
        ...


class IncidentEscalationEngine(ABC):
    """
    Abstract interface for Safety Incident Escalation Queue.
    PRD §3.3: 15-minute SLA deadline on self-harm / abuse disclosures.
    GUARDRAILS G-003: Fallback SMS paging when DB connection fails.
    """

    @abstractmethod
    async def create_incident(
        self,
        *,
        learner_id: UUID,
        tenant_id: UUID,
        category: str,
        transcript_excerpt: str,
    ) -> SafetyIncident:
        """Create incident with 15-minute SLA deadline."""
        ...

    @abstractmethod
    async def acknowledge_incident(
        self, *, incident_id: str, reviewer_id: str
    ) -> SafetyIncident:
        """Mark incident acknowledged by human reviewer."""
        ...

    @abstractmethod
    async def trigger_sms_fallback_paging(self, *, incident: SafetyIncident) -> bool:
        """Send direct SMS/webhook paging when DB is offline (GUARDRAILS G-003)."""
        ...


class RetentionSchedulerEngine(ABC):
    """
    Abstract interface for Memory Pruning and Legal Holds.
    PRD §3.4: 18-month memory expiry, 7-year legal hold on safety incidents.
    """

    @abstractmethod
    async def prune_expired_memories(self, *, retention_days: int = 540) -> int:
        """Prune memories older than 18 months (540 days)."""
        ...

    @abstractmethod
    async def execute_immediate_consent_purge(self, *, learner_id: UUID) -> int:
        """Executes immediate memory purge upon consent revocation (PRD §3.4)."""
        ...
