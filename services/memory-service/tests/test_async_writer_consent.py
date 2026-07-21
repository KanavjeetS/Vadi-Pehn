"""
Unit tests for AsyncMemoryWriter (`services/memory-service/tests/test_async_writer_consent.py`).
Verifies mandatory consent verification (`PRD §3.2`), 18-month TTL setting (`PRD §3.4`),
and non-blocking background task scheduling (`PRD §4.2`).
"""

import asyncio
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from mock_db import MockAsyncpgConnection, MockAsyncpgPool
from memory_service.abstractions import ConsentCheckerClient
from memory_service.chunker import SentenceBoundaryChunker
from memory_service.embeddings import MockEmbeddingClient
from memory_service.write_pipeline import AsyncMemoryWriter, ConsentDeniedWriteAbort


class MockConsentChecker(ConsentCheckerClient):
    def __init__(self, is_active: bool = True) -> None:
        self.is_active = is_active

    async def check_memory_write_consent(
        self, tenant_id: UUID, learner_id: UUID
    ) -> bool:
        return self.is_active


@pytest.mark.asyncio
async def test_writer_aborts_immediately_when_consent_revoked_or_missing():
    mock_pool = MagicMock() if "MagicMock" in globals() else object()
    # Actually, we can use a dummy object or MockAsyncpgPool with no connection accesses
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)
    checker = MockConsentChecker(is_active=False)
    writer = AsyncMemoryWriter(pool=mock_pool, consent_checker=checker)

    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    learner_id = UUID("22222222-2222-2222-2222-222222222222")

    with pytest.raises(ConsentDeniedWriteAbort):
        await writer.write_memory_chunked(
            tenant_id=tenant_id,
            learner_id=learner_id,
            content="This should never be written to postgres.",
        )

    # Verify no execution queries were recorded
    assert len(mock_conn.executed_queries) == 0


@pytest.mark.asyncio
async def test_writer_inserts_chunks_with_18_month_ttl_when_consent_active():
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    # Simulate two inserted chunk IDs
    mock_conn.fetchval_returns = [
        UUID("10000000-0000-0000-0000-000000000001"),
        UUID("10000000-0000-0000-0000-000000000002"),
    ]

    checker = MockConsentChecker(is_active=True)
    writer = AsyncMemoryWriter(
        pool=mock_pool,
        consent_checker=checker,
        embedding_client=MockEmbeddingClient(),
        chunker=SentenceBoundaryChunker(max_chunk_chars=40, overlap_sentences=0),
    )

    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    learner_id = UUID("22222222-2222-2222-2222-222222222222")
    text = "First chunk here. Second chunk goes here cleanly."

    ids = await writer.write_memory_chunked(
        tenant_id=tenant_id,
        learner_id=learner_id,
        content=text,
    )

    assert len(ids) == 2
    # Verify RLS and 18-month TTL in SQL (540 days)
    executed_sql = [q[0] for q in mock_conn.executed_queries]
    assert any("SET LOCAL app.current_tenant_id" in sql for sql in executed_sql)

    insert_calls = [q[0] for q in mock_conn.fetchval_queries]
    assert len(insert_calls) == 2
    for sql in insert_calls:
        assert "INTERVAL '540 days'" in sql or "540 days" in sql
        assert "INSERT INTO learner_memories" in sql


@pytest.mark.asyncio
async def test_writer_async_background_task_scheduling():
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)
    mock_conn.fetchval_returns = [UUID("10000000-0000-0000-0000-000000000001")]

    writer = AsyncMemoryWriter(
        pool=mock_pool, consent_checker=MockConsentChecker(is_active=True)
    )

    task = writer.write_memory_async(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        learner_id=UUID("22222222-2222-2222-2222-222222222222"),
        content="Async background chunk.",
    )

    assert isinstance(task, asyncio.Task)
    res = await task
    assert len(res) == 1
