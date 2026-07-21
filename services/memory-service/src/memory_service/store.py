"""
PostgreSQL + pgvector implementation of MemoryStore.
Implements: SD §3.2 (learner_memories table), SD §7.1 (transactional RLS + HNSW settings).
PRD §3.4 (18-month retention pruning & consent-withdrawal deletion).

CRITICAL INVARIANT (GUARDRAILS G-002):
Every query or write against learner_memories MUST run inside a transaction where
`SET LOCAL app.current_tenant_id = $1` has been executed. Never trust application-level
WHERE clauses alone.
"""

from __future__ import annotations

import json
from datetime import timezone
from typing import Any
from uuid import UUID

import asyncpg

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from services.abstractions import MemoryChunk, MemoryStore


class PostgresMemoryStore(MemoryStore):
    """
    Production connection-pooled implementation of MemoryStore using asyncpg and pgvector.
    Requires an asyncpg.Pool initialized against the Memory Service PostgreSQL database.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Write a memory chunk inside an RLS-scoped transaction.
        Returns the stringified ID of the newly created memory row.
        """
        embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
        metadata_json = json.dumps(metadata or {})
        session_id = (metadata or {}).get(
            "session_id", str(learner_id)
        )  # fallback if session_id not in metadata

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. Enforce RLS for this transaction (GUARDRAILS G-002)
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )

                # 2. Insert memory row
                row_id = await conn.fetchval(
                    """
                    INSERT INTO learner_memories (
                        tenant_id,
                        learner_id,
                        conversation_session_id,
                        embedding,
                        content,
                        metadata
                    ) VALUES ($1, $2, $3, $4::vector, $5, $6::jsonb)
                    RETURNING id
                    """,
                    tenant_id,
                    learner_id,
                    (
                        UUID(session_id)
                        if isinstance(session_id, str) and len(session_id) == 36
                        else learner_id
                    ),
                    embedding_str,
                    content,
                    metadata_json,
                )
                return str(row_id)

    async def query(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[MemoryChunk]:
        """
        Retrieve top-k similar chunks for this learner inside an RLS-scoped transaction.
        Sets hnsw.iterative_scan and hnsw.max_scan_tuples per SD §7.1.
        """
        embedding_str = "[" + ",".join(str(f) for f in query_embedding) + "]"

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. Enforce RLS and vector search parameters inside transaction (SD §7.1)
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")

                # 2. Execute HNSW approximate nearest neighbor search
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        tenant_id,
                        learner_id,
                        content,
                        embedding::text AS embedding_text,
                        created_at,
                        1 - (embedding <=> $1::vector) AS similarity_score
                    FROM learner_memories
                    WHERE learner_id = $2
                      AND expires_at > NOW()
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                    """,
                    embedding_str,
                    learner_id,
                    k,
                )

                chunks: list[MemoryChunk] = []
                for row in rows:
                    # Parse pgvector string "[0.1,0.2,...]" back to list[float]
                    raw_vec = row["embedding_text"].strip("[]")
                    vec = [float(x) for x in raw_vec.split(",") if x.strip()]

                    chunks.append(
                        MemoryChunk(
                            chunk_id=str(row["id"]),
                            content=row["content"],
                            embedding=vec,
                            tenant_id=row["tenant_id"],
                            learner_id=row["learner_id"],
                            created_at=(
                                row["created_at"]
                                if row["created_at"].tzinfo
                                else row["created_at"].replace(tzinfo=timezone.utc)
                            ),
                            similarity_score=float(row["similarity_score"]),
                        )
                    )
                return chunks

    async def delete_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> int:
        """
        Delete ALL memories for a learner inside an RLS-scoped transaction.
        Triggered when guardian revokes 'conversation_storage' consent (PRD §3.2, §3.4).
        Returns count of deleted rows.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                status = await conn.execute(
                    """
                    DELETE FROM learner_memories
                    WHERE learner_id = $1
                    """,
                    learner_id,
                )
                # status string is "DELETE <count>"
                parts = status.split()
                return int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 0

    async def prune_expired(self, *, retention_months: int = 18) -> int:
        """
        Nightly pruning job — deletes memories across all tenants where `expires_at < NOW()`.
        PRD §3.4: 18 months rolling retention.
        Note: Since this is a system maintenance job across all expired rows, it runs directly
        or with appropriate database superuser privileges or without setting app.current_tenant_id
        if RLS allows system role cleanup. For our table where FORCE RLS is active, pruning
        should be executed by a system role bypassing RLS or iterates tenants.
        If the connection pool user is subject to FORCE RLS, we iterate distinct tenants or execute
        via bypass role. Here we iterate distinct tenants or execute standard delete if role bypasses.
        """
        async with self._pool.acquire() as conn:
            # Check if current user bypasses RLS or if we need per-tenant transactions
            # Since FORCE RLS is on, let's query all tenant IDs first (tenants table has no RLS)
            tenant_ids = await conn.fetch("SELECT id FROM tenants")
            total_deleted = 0
            for record in tenant_ids:
                tid = record["id"]
                async with conn.transaction():
                    await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tid))
                    status = await conn.execute("""
                        DELETE FROM learner_memories
                        WHERE expires_at <= NOW()
                        """)
                    parts = status.split()
                    count = (
                        int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 0
                    )
                    total_deleted += count
            return total_deleted
