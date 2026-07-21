"""
Unit tests for ContextualRetrievalService (`services/memory-service/tests/test_contextual_rapport.py`).
Verifies session dialogue recency window and rapport-gated career panel introductions (PRD §4.3).
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from mock_db import MockAsyncpgConnection, MockAsyncpgPool
from memory_service.abstractions import HybridRetrievalQuery, ScoredMemoryItem
from memory_service.context import ContextualRetrievalService
from memory_service.retrieval import HybridRetrievalEngine


@pytest.mark.asyncio
async def test_rapport_gated_panel_blocked_when_score_below_threshold():
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    # Setup mock hybrid retrieval engine returning one item
    mock_engine = MagicMock(spec=HybridRetrievalEngine)
    mock_engine.retrieve_hybrid = AsyncMock(
        return_value=[
            ScoredMemoryItem(
                memory_id="1",
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                learner_id=UUID("22222222-2222-2222-2222-222222222222"),
                content="Past tutoring memory",
            )
        ]
    )

    # Session history returns 2 turns
    session_rows = [
        {"content": "Hi Vadi!", "metadata": '{"role": "user"}'},
        {"content": "Hello! Ready for algebra?", "metadata": '{"role": "assistant"}'},
    ]
    mock_conn.fetch_returns = [session_rows]

    # Rapport query returns 45.0 (below 70.0 threshold)
    mock_conn.fetchval_returns = [45.0]

    service = ContextualRetrievalService(
        pool=mock_pool,
        retrieval_engine=mock_engine,
        rapport_threshold=70.0,
    )

    query = HybridRetrievalQuery(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        learner_id=UUID("22222222-2222-2222-2222-222222222222"),
        query_text="Tell me about careers in AI",
        query_embedding=[0.0] * 1536,
        session_id=UUID("33333333-3333-3333-3333-333333333333"),
    )

    summary = await service.get_contextual_summary(query)

    assert summary.rapport_score == 45.0
    assert summary.panel_introduced is False
    assert len(summary.matched_personas) == 0
    assert len(summary.session_history) == 2


@pytest.mark.asyncio
async def test_rapport_gated_panel_introduced_when_score_meets_threshold():
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    mock_engine = MagicMock(spec=HybridRetrievalEngine)
    mock_engine.retrieve_hybrid = AsyncMock(return_value=[])

    # First fetch: session turns (empty), second fetch: learner topics, third fetch: professional personas
    mock_conn.fetch_returns = [
        [],  # session rows
        [{"topics": '["robotics", "ai"]'}],  # interest profile rows
        [
            {
                "id": UUID("44444444-4444-4444-4444-444444444444"),
                "persona_name": "Dr. Kavita (Robotics Engineer)",
                "career_domain": "robotics",
                "bio": "Expert in autonomous drones and robotics.",
            }
        ],
    ]
    # Rapport returns 82.5 (above 70.0 threshold)
    mock_conn.fetchval_returns = [82.5]

    service = ContextualRetrievalService(
        pool=mock_pool,
        retrieval_engine=mock_engine,
        rapport_threshold=70.0,
    )

    query = HybridRetrievalQuery(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        learner_id=UUID("22222222-2222-2222-2222-222222222222"),
        query_text="What is robotics?",
        query_embedding=[0.0] * 1536,
        session_id=UUID("33333333-3333-3333-3333-333333333333"),
    )

    summary = await service.get_contextual_summary(query)

    assert summary.rapport_score == 82.5
    assert summary.panel_introduced is True
    assert len(summary.matched_personas) == 1
    assert (
        summary.matched_personas[0]["persona_name"] == "Dr. Kavita (Robotics Engineer)"
    )


@pytest.mark.asyncio
async def test_revoked_consent_filtering():
    """
    PRD §3.4 / §3.5 CONSENT LEDGER AUDIT ASSERTION:
    Proves that memory chunks tagged with revoked consent categories are excluded from retrieved memories.
    """
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    mock_engine = MagicMock(spec=HybridRetrievalEngine)
    mock_engine.retrieve_hybrid = AsyncMock(
        return_value=[
            ScoredMemoryItem(
                memory_id="1",
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                learner_id=UUID("22222222-2222-2222-2222-222222222222"),
                content="Normal tutoring memory",
                metadata={"consent_category": "conversation_storage"},
            ),
            ScoredMemoryItem(
                memory_id="2",
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                learner_id=UUID("22222222-2222-2222-2222-222222222222"),
                content="Ingested report card document text",
                metadata={"consent_category": "document_ingestion"},
            ),
        ]
    )

    mock_conn.fetch_returns = [[]]
    mock_conn.fetchval_returns = [50.0]

    service = ContextualRetrievalService(pool=mock_pool, retrieval_engine=mock_engine)
    query = HybridRetrievalQuery(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        learner_id=UUID("22222222-2222-2222-2222-222222222222"),
        query_text="algebra test",
        query_embedding=[0.0] * 1536,
    )

    # When 'document_ingestion' consent is REVOKED
    summary = await service.get_contextual_summary(
        query, revoked_consent_categories=["document_ingestion"]
    )

    # Memory #2 (document_ingestion) must be excluded!
    assert len(summary.retrieved_memories) == 1
    assert summary.retrieved_memories[0].content == "Normal tutoring memory"


@pytest.mark.asyncio
async def test_revoked_consent_filtering_excludes_session_history():
    """Revoked consent categories must not re-enter context through recency history."""
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)
    mock_engine = MagicMock(spec=HybridRetrievalEngine)
    mock_engine.retrieve_hybrid = AsyncMock(return_value=[])
    mock_conn.fetch_returns = [
        [
            {"content": "visible synthetic turn", "metadata": '{"role":"user"}'},
            {
                "content": "revoked synthetic document turn",
                "metadata": '{"role":"assistant","consent_category":"document_ingestion"}',
            },
        ]
    ]
    mock_conn.fetchval_returns = [10.0]

    service = ContextualRetrievalService(pool=mock_pool, retrieval_engine=mock_engine)
    query = HybridRetrievalQuery(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        learner_id=UUID("22222222-2222-2222-2222-222222222222"),
        query_text="synthetic query",
        query_embedding=[0.0] * 1536,
        session_id=UUID("33333333-3333-3333-3333-333333333333"),
    )

    summary = await service.get_contextual_summary(
        query, revoked_consent_categories=["document_ingestion"]
    )

    assert [item["content"] for item in summary.session_history] == [
        "visible synthetic turn"
    ]
