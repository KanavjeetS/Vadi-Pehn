"""
Consent Ledger implementation for Governance Service.
Implements: PRD §3.2 (Granular Consent Ledger & Immediate Revocation Purge).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Awaitable
from uuid import UUID

from governance_service.abstractions import ConsentLedgerEngine
from governance_service.models import ConsentRecord, ConsentUpdatePayload

import asyncpg


class ConsentLedger(ConsentLedgerEngine):
    """
    Manages consent records for learners.
    Triggers immediate data purge if conversation storage consent is revoked.
    """

    def __init__(
        self, purge_callback: Callable[[UUID], Awaitable[int]] | None = None
    ) -> None:
        self._ledger: dict[str, ConsentRecord] = {}
        self.purge_callback = purge_callback

    async def get_consent_record(self, *, learner_id: UUID) -> ConsentRecord:
        key = str(learner_id)
        if key not in self._ledger:
            # Default active consent for new accounts
            self._ledger[key] = ConsentRecord(
                learner_id=learner_id,
                guardian_id=learner_id,  # Simplified default for dev
                conversation_storage=True,
                document_ingestion=True,
                voice_recording=True,
                career_introductions=True,
                updated_at=datetime.now(timezone.utc),
            )
        return self._ledger[key]

    async def update_consent(
        self,
        *,
        learner_id: UUID,
        payload: ConsentUpdatePayload,
    ) -> ConsentRecord:
        current = await self.get_consent_record(learner_id=learner_id)
        now = datetime.now(timezone.utc)

        prev_storage = current.conversation_storage
        new_storage = (
            payload.conversation_storage
            if payload.conversation_storage is not None
            else current.conversation_storage
        )

        updated_record = ConsentRecord(
            learner_id=learner_id,
            guardian_id=current.guardian_id,
            conversation_storage=new_storage,
            document_ingestion=(
                payload.document_ingestion
                if payload.document_ingestion is not None
                else current.document_ingestion
            ),
            voice_recording=(
                payload.voice_recording
                if payload.voice_recording is not None
                else current.voice_recording
            ),
            career_introductions=(
                payload.career_introductions
                if payload.career_introductions is not None
                else current.career_introductions
            ),
            updated_at=now,
        )

        self._ledger[str(learner_id)] = updated_record

        # PRD §3.4 REQUIREMENT: Immediate data purge upon consent withdrawal
        if prev_storage and not new_storage and self.purge_callback:
            await self.purge_callback(learner_id)

        return updated_record


class PostgresConsentLedger(ConsentLedgerEngine):
    """Persistent governance consent ledger with transaction-local tenant RLS."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_consent_record(
        self, *, learner_id: UUID, tenant_id: UUID | None = None
    ) -> ConsentRecord:
        if tenant_id is None:
            raise ValueError("tenant_id is required for persistent consent reads")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                row = await conn.fetchrow(
                    """
                    SELECT tenant_id, learner_id, guardian_id, conversation_storage,
                           document_ingestion, voice_recording, career_introductions, updated_at
                    FROM consent_records WHERE tenant_id = $1 AND learner_id = $2
                    """,
                    tenant_id,
                    learner_id,
                )
                if row is None:
                    raise KeyError(f"Consent record missing for learner {learner_id}")
                return ConsentRecord(**dict(row))

    async def update_consent(
        self,
        *,
        learner_id: UUID,
        payload: ConsentUpdatePayload,
        tenant_id: UUID | None = None,
        guardian_id: UUID | None = None,
    ) -> ConsentRecord:
        if tenant_id is None or guardian_id is None:
            raise ValueError(
                "tenant_id and guardian_id are required for persistent consent writes"
            )
        fields = payload.model_dump(exclude_none=True)
        if not fields:
            return await self.get_consent_record(
                learner_id=learner_id, tenant_id=tenant_id
            )
        assignments = ", ".join(
            f"{key} = ${index + 4}" for index, key in enumerate(fields)
        )
        values = list(fields.values())
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO consent_records (tenant_id, learner_id, guardian_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (tenant_id, learner_id) DO UPDATE SET {assignments}, updated_at = NOW()
                    RETURNING tenant_id, learner_id, guardian_id, conversation_storage,
                              document_ingestion, voice_recording, career_introductions, updated_at
                    """,
                    tenant_id,
                    learner_id,
                    guardian_id,
                    *values,
                )
                return ConsentRecord(**dict(row))

    async def summary(self, *, tenant_id: UUID) -> dict[str, bool]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(bool_and(conversation_storage), FALSE) AS conversation_storage,
                           COALESCE(bool_and(document_ingestion), FALSE) AS document_ingestion,
                           COALESCE(bool_and(voice_recording), FALSE) AS voice_recording,
                           COALESCE(bool_and(career_introductions), FALSE) AS career_introductions
                    FROM consent_records WHERE tenant_id = $1
                    """,
                    tenant_id,
                )
                return dict(row)
