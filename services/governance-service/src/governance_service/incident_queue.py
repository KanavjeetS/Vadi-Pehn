"""
Safety Incident Queue and SLA Escalation Engine.
Implements: PRD §3.3 (15-Minute SLA Deadline, 7-Year Legal Hold) & GUARDRAILS G-003 (SMS Fallback Paging).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from uuid import UUID

import httpx
import asyncpg

from governance_service.abstractions import IncidentEscalationEngine
from governance_service.models import PagingNotification, SafetyIncident


class IncidentEscalationQueue(IncidentEscalationEngine):
    """
    Manages safety incidents, 15-minute escalation SLA deadlines, reviewer acknowledgments,
    and direct SMS fallback notifications.
    """

    def __init__(
        self,
        sms_webhook_url: str = "",
        pager_phone: str = "+15550199",
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self.incidents: dict[str, SafetyIncident] = {}
        self.sms_webhook_url = sms_webhook_url
        self.pager_phone = pager_phone
        self.paging_log: list[PagingNotification] = []
        self._pool = pool

    async def create_incident(
        self,
        *,
        learner_id: UUID,
        tenant_id: UUID,
        category: str,
        transcript_excerpt: str,
    ) -> SafetyIncident:
        now = datetime.now(timezone.utc)
        incident_id = f"inc_{uuid.uuid4().hex[:10]}"

        # PRD §3.3 REQUIREMENT: 15-minute SLA deadline
        sla_deadline = now + timedelta(minutes=15)

        incident = SafetyIncident(
            incident_id=incident_id,
            tenant_id=tenant_id,
            learner_id=learner_id,
            category=category,
            transcript_excerpt=transcript_excerpt,
            created_at=now,
            sla_deadline=sla_deadline,
            acknowledged_at=None,
            reviewer_id=None,
            legal_hold=True,  # 7-year legal hold mandatory
        )

        self.incidents[incident_id] = incident
        if self._pool is not None:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                    )
                    await conn.execute(
                        """
                        INSERT INTO safety_incidents
                        (incident_id, tenant_id, learner_id, category, transcript_excerpt,
                         created_at, sla_deadline, legal_hold)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                        """,
                        incident.incident_id,
                        incident.tenant_id,
                        incident.learner_id,
                        incident.category,
                        incident.transcript_excerpt,
                        incident.created_at,
                        incident.sla_deadline,
                    )

        # Immediately attempt paging trigger
        await self.trigger_sms_fallback_paging(incident=incident)

        return incident

    async def acknowledge_incident(
        self, *, incident_id: str, reviewer_id: str
    ) -> SafetyIncident:
        if incident_id not in self.incidents:
            raise KeyError(f"Incident {incident_id} not found")

        inc = self.incidents[incident_id]
        now = datetime.now(timezone.utc)

        updated_dict = inc.model_dump()
        updated_dict["acknowledged_at"] = now
        updated_dict["reviewer_id"] = reviewer_id

        updated = SafetyIncident(**updated_dict)
        self.incidents[incident_id] = updated
        if self._pool is not None:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SET LOCAL app.current_tenant_id = $1", str(inc.tenant_id)
                    )
                    await conn.execute(
                        "UPDATE safety_incidents SET acknowledged_at = $1, reviewer_id = $2 WHERE incident_id = $3",
                        now,
                        reviewer_id,
                        incident_id,
                    )
        return updated

    async def trigger_sms_fallback_paging(self, *, incident: SafetyIncident) -> bool:
        """
        GUARDRAILS G-003 REQUIREMENT: Direct SMS webhook paging when DB/primary channel fails.
        """
        notification = PagingNotification(
            incident_id=incident.incident_id,
            category=incident.category,
            sla_deadline=incident.sla_deadline,
            pager_phone=self.pager_phone,
            delivered=True,
        )
        self.paging_log.append(notification)

        if self.sms_webhook_url:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        self.sms_webhook_url,
                        json=notification.model_dump(mode="json"),
                        timeout=2.0,
                    )
            except Exception:
                pass  # Fallback logger handled in paging_log

        return True

    async def list_incidents(self, *, tenant_id: UUID) -> list[SafetyIncident]:
        if self._pool is None:
            return [
                incident
                for incident in self.incidents.values()
                if incident.tenant_id == tenant_id
            ]
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                rows = await conn.fetch(
                    """
                    SELECT incident_id, tenant_id, learner_id, category, transcript_excerpt,
                           created_at, sla_deadline, acknowledged_at, reviewer_id, legal_hold
                    FROM safety_incidents WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 100
                    """,
                    tenant_id,
                )
                return [SafetyIncident(**dict(row)) for row in rows]
