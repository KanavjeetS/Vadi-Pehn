"""
Unit and integration tests for PostgresMemoryStore and RLS tenant isolation.
Implements: PRD §14 (testing strategy — RLS / tenant isolation), GUARDRAILS G-002 verification.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.abstractions import InMemoryVectorStore
from memory_service.store import PostgresMemoryStore


# ─────────────────────────────────────────────────────────────────────────────
# Mock asyncpg Pool & Connection for fast unit testing of SQL query structure
# ─────────────────────────────────────────────────────────────────────────────

class MockAsyncpgTransaction:
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): pass

class MockAsyncpgConnection:
    def __init__(self):
        self.executed_queries: list[tuple[str, tuple]] = []
        self.fetched_queries: list[tuple[str, tuple]] = []
        self.fetchval_queries: list[tuple[str, tuple]] = []
        self.current_settings: dict[str, str] = {}

    def transaction(self) -> MockAsyncpgTransaction:
        return MockAsyncpgTransaction()

    async def execute(self, query: str, *args) -> str:
        self.executed_queries.append((query.strip(), args))
        if query.strip().startswith("SET LOCAL app.current_tenant_id ="):
            self.current_settings["app.current_tenant_id"] = args[0]
        return "DELETE 2" if "DELETE FROM learner_memories" in query else "OK"

    async def fetchval(self, query: str, *args) -> Any:
        self.fetchval_queries.append((query.strip(), args))
        return 12345

    async def fetch(self, query: str, *args) -> list[dict[str, Any]]:
        self.fetched_queries.append((query.strip(), args))
        if "SELECT id FROM tenants" in query:
            return [{"id": uuid4()}, {"id": uuid4()}]
        # Return mock row for query
        return [{
            "id": 1,
            "tenant_id": args[1] if len(args) > 1 else uuid4(),
            "learner_id": args[1] if len(args) > 1 else uuid4(),
            "content": "Mock memory text",
            "embedding_text": "[0.1, 0.2, 0.3]",
            "created_at": datetime.now(timezone.utc),
            "similarity_score": 0.95
        }]

class MockAsyncpgPoolContext:
    def __init__(self, conn: MockAsyncpgConnection):
        self.conn = conn
    async def __aenter__(self) -> MockAsyncpgConnection:
        return self.conn
    async def __aexit__(self, exc_type, exc, tb): pass

class MockAsyncpgPool:
    def __init__(self):
        self.conn = MockAsyncpgConnection()
    def acquire(self) -> MockAsyncpgPoolContext:
        return MockAsyncpgPoolContext(self.conn)


# ─────────────────────────────────────────────────────────────────────────────
# UNIT TESTS (Verify SQL/RLS SET LOCAL parameters without external DB)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_postgres_store_write_sets_tenant_rls():
    """Verify write() issues SET LOCAL app.current_tenant_id inside transaction before INSERT."""
    pool = MockAsyncpgPool()
    store = PostgresMemoryStore(pool)  # type: ignore
    tenant_id = uuid4()
    learner_id = uuid4()

    row_id = await store.write(
        tenant_id=tenant_id,
        learner_id=learner_id,
        content="Test content",
        embedding=[0.1, 0.2, 0.3],
        metadata={"session_id": str(uuid4())}
    )

    assert row_id == "12345"
    assert len(pool.conn.executed_queries) >= 1
    # Check that SET LOCAL was executed
    set_local_cmd, set_local_args = pool.conn.executed_queries[0]
    assert "SET LOCAL app.current_tenant_id = $1" in set_local_cmd
    assert set_local_args[0] == str(tenant_id)


@pytest.mark.asyncio
async def test_postgres_store_query_sets_rls_and_hnsw_params():
    """Verify query() sets RLS and HNSW scan parameters per SD §7.1."""
    pool = MockAsyncpgPool()
    store = PostgresMemoryStore(pool)  # type: ignore
    tenant_id = uuid4()
    learner_id = uuid4()

    chunks = await store.query(
        tenant_id=tenant_id,
        learner_id=learner_id,
        query_embedding=[0.1, 0.2, 0.3],
        k=3
    )

    assert len(chunks) == 1
    assert chunks[0].content == "Mock memory text"
    assert chunks[0].similarity_score == 0.95

    executed = [q[0] for q in pool.conn.executed_queries]
    assert any("SET LOCAL app.current_tenant_id = $1" in q for q in executed)
    assert any("SET LOCAL hnsw.iterative_scan = relaxed_order" in q for q in executed)
    assert any("SET LOCAL hnsw.max_scan_tuples = 20000" in q for q in executed)


@pytest.mark.asyncio
async def test_postgres_store_delete_for_learner():
    """Verify delete_for_learner sets RLS and issues DELETE query."""
    pool = MockAsyncpgPool()
    store = PostgresMemoryStore(pool)  # type: ignore
    tenant_id = uuid4()
    learner_id = uuid4()

    deleted_count = await store.delete_for_learner(tenant_id=tenant_id, learner_id=learner_id)
    assert deleted_count == 2
    executed = [q[0] for q in pool.conn.executed_queries]
    assert any("SET LOCAL app.current_tenant_id = $1" in q for q in executed)
    assert any("DELETE FROM learner_memories" in q for q in executed)


@pytest.mark.asyncio
async def test_postgres_store_prune_expired():
    """Verify prune_expired iterates across tenants and deletes expired rows."""
    pool = MockAsyncpgPool()
    store = PostgresMemoryStore(pool)  # type: ignore

    pruned = await store.prune_expired(retention_months=18)
    assert pruned == 4  # 2 tenants * 2 deleted rows
    executed = [q[0] for q in pool.conn.executed_queries]
    assert any("SET LOCAL app.current_tenant_id = $1" in q for q in executed)
    assert any("DELETE FROM learner_memories" in q and "expires_at <= NOW()" in q for q in executed)
