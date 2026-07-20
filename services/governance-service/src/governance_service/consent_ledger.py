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


class ConsentLedger(ConsentLedgerEngine):
    """
    Manages consent records for learners.
    Triggers immediate data purge if conversation storage consent is revoked.
    """

    def __init__(
        self,
        purge_callback: Callable[[UUID], Awaitable[int]] | None = None
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
        new_storage = payload.conversation_storage if payload.conversation_storage is not None else current.conversation_storage

        updated_record = ConsentRecord(
            learner_id=learner_id,
            guardian_id=current.guardian_id,
            conversation_storage=new_storage,
            document_ingestion=payload.document_ingestion if payload.document_ingestion is not None else current.document_ingestion,
            voice_recording=payload.voice_recording if payload.voice_recording is not None else current.voice_recording,
            career_introductions=payload.career_introductions if payload.career_introductions is not None else current.career_introductions,
            updated_at=now,
        )

        self._ledger[str(learner_id)] = updated_record

        # PRD §3.4 REQUIREMENT: Immediate data purge upon consent withdrawal
        if prev_storage and not new_storage and self.purge_callback:
            await self.purge_callback(learner_id)

        return updated_record
