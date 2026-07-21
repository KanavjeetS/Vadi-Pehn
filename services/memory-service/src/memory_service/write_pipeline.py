"""
Asynchronous memory ingestion pipeline with mandatory Governance Consent checking
and 18-month TTL enforcement (`services/memory-service/write_pipeline.py`).
Implements: PRD §3.2 (Consent checks before storage), PRD §3.4 (18-month retention TTL),
SD §3.1 & §5.1, implementation_plan.md §4D.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import asyncpg

from memory_service.abstractions import ConsentCheckerClient, EmbeddingClient
from memory_service.chunker import SentenceBoundaryChunker
from memory_service.embeddings import MockEmbeddingClient

logger = logging.getLogger("memory_service.write_pipeline")


class ConsentDeniedWriteAbort(Exception):
    """Raised when memory ingestion is attempted without active parental/learner consent."""

    pass


class PostgresConsentChecker(ConsentCheckerClient):
    """
    Checks the Governance Service consent ledger (`consent_records` table) inside an RLS-scoped query.
    Returns True only if active consent exists for scope 'memory_storage' or 'all'.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def check_memory_write_consent(
        self, tenant_id: UUID, learner_id: UUID
    ) -> bool:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Enforce RLS on consent verification
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                status = await conn.fetchval(
                    """
                    SELECT status FROM consent_records
                    WHERE learner_id = $1
                      AND tenant_id = $2
                      AND scope IN ('memory_storage', 'all')
                    ORDER BY granted_at DESC
                    LIMIT 1
                    """,
                    learner_id,
                    tenant_id,
                )
                return status == "active"


class AsyncMemoryWriter:
    """
    Handles non-blocking, sentence-aware chunking and ingestion of learner dialogue into pgvector.
    Enforces mandatory consent checks (`PRD §3.2`) and 18-month retention TTL (`PRD §3.4`).
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        consent_checker: ConsentCheckerClient | None = None,
        embedding_client: EmbeddingClient | None = None,
        chunker: SentenceBoundaryChunker | None = None,
    ) -> None:
        self._pool = pool
        self.consent_checker = consent_checker or PostgresConsentChecker(pool)
        self.embedding_client = embedding_client or MockEmbeddingClient()
        self.chunker = chunker or SentenceBoundaryChunker()

    async def write_memory_chunked(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        content: str,
        session_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Synchronous-like async call to verify consent, chunk dialogue, generate embeddings,
        and write rows to `learner_memories` with 18-month TTL inside an RLS transaction.
        Returns list of newly inserted row IDs.
        Raises `ConsentDeniedWriteAbort` if consent check returns False.
        """
        # 1. Mandatory Governance Consent Gate (PRD §3.2)
        has_consent = await self.consent_checker.check_memory_write_consent(
            tenant_id, learner_id
        )
        if not has_consent:
            logger.warning(
                f"ConsentDeniedWriteAbort: Learner {learner_id} (Tenant {tenant_id}) lacks active memory_storage consent. Write aborted."
            )
            raise ConsentDeniedWriteAbort(f"No active consent for learner {learner_id}")

        # 2. Sentence-boundary-aware chunking (implementation_plan.md §4A)
        chunks = self.chunker.chunk_text(content)
        if not chunks:
            return []

        # 3. Generate batch embedding vectors
        embeddings = await self.embedding_client.embed_batch(chunks)

        inserted_ids: list[str] = []
        base_meta = metadata or {}

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Enforce RLS for write transaction (GUARDRAILS G-002)
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )

                for chunk_text, vec in zip(chunks, embeddings):
                    embedding_str = "[" + ",".join(str(f) for f in vec) + "]"
                    meta_copy = dict(base_meta)
                    meta_copy["chunk_len"] = len(chunk_text)
                    if session_id:
                        meta_copy["session_id"] = str(session_id)
                    metadata_json = json.dumps(meta_copy)

                    # 4. Insert row with 18-month TTL (expires_at = NOW() + INTERVAL '540 days') (PRD §3.4)
                    row_id = await conn.fetchval(
                        """
                        INSERT INTO learner_memories (
                            tenant_id,
                            learner_id,
                            conversation_session_id,
                            embedding,
                            content,
                            metadata,
                            expires_at
                        ) VALUES (
                            $1, $2, $3, $4::vector, $5, $6::jsonb,
                            NOW() + INTERVAL '540 days'
                        )
                        RETURNING id
                        """,
                        tenant_id,
                        learner_id,
                        session_id or learner_id,
                        embedding_str,
                        chunk_text,
                        metadata_json,
                    )
                    inserted_ids.append(str(row_id))

        return inserted_ids

    def write_memory_async(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        content: str,
        session_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> asyncio.Task[list[str]]:
        """
        Schedules `write_memory_chunked` as a non-blocking background `asyncio.Task` (`PRD §4.2`).
        Never blocks the live response path.
        """
        task = asyncio.create_task(
            self.write_memory_chunked(
                tenant_id=tenant_id,
                learner_id=learner_id,
                content=content,
                session_id=session_id,
                metadata=metadata,
            )
        )
        return task
