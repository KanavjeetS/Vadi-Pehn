"""
Unit tests for HybridRetrievalEngine (`services/memory-service/tests/test_retrieval_hybrid.py`).
Verifies HNSW dense scoring, full-text BM25 sparse scoring, Reciprocal Rank Fusion (RRF),
and RLS transaction scoping (`SET LOCAL app.current_tenant_id = $1`).
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from mock_db import MockAsyncpgConnection, MockAsyncpgPool
from memory_service.abstractions import HybridRetrievalQuery
from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient
from memory_service.retrieval import HybridRetrievalEngine


@pytest.mark.asyncio
async def test_hybrid_retrieval_engine_merges_dense_and_sparse_with_rrf():
    # Setup mock connection pool and transaction using mock_db helper classes
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    learner_id = UUID("22222222-2222-2222-2222-222222222222")

    # Dense returns items A and B
    dense_rows = [
        {
            "id": "item-a",
            "tenant_id": tenant_id,
            "learner_id": learner_id,
            "content": "Dense hit A content",
            "metadata": '{"source": "dense"}',
            "created_at": datetime.now(timezone.utc),
            "dense_score": 0.88,
        },
        {
            "id": "item-b",
            "tenant_id": tenant_id,
            "learner_id": learner_id,
            "content": "Dense hit B content",
            "metadata": '{"source": "dense"}',
            "created_at": datetime.now(timezone.utc),
            "dense_score": 0.75,
        },
    ]

    # Sparse returns items B and C
    sparse_rows = [
        {
            "id": "item-b",
            "tenant_id": tenant_id,
            "learner_id": learner_id,
            "content": "Dense hit B content",
            "metadata": '{"source": "sparse"}',
            "created_at": datetime.now(timezone.utc),
            "sparse_score": 1.45,
        },
        {
            "id": "item-c",
            "tenant_id": tenant_id,
            "learner_id": learner_id,
            "content": "Sparse hit C exact keyword match",
            "metadata": '{"source": "sparse"}',
            "created_at": datetime.now(timezone.utc),
            "sparse_score": 0.95,
        },
    ]

    mock_conn.fetch_returns = [dense_rows, sparse_rows]

    engine = HybridRetrievalEngine(
        pool=mock_pool,
        embedding_client=MockEmbeddingClient(),
        reranker_client=MockRerankerClient(),
    )

    query = HybridRetrievalQuery(
        tenant_id=tenant_id,
        learner_id=learner_id,
        query_text="exact keyword query",
        query_embedding=[0.1] * 1536,
        top_k=3,
        rrf_k=60,
    )

    results = await engine.retrieve_hybrid(query)

    # Verify RLS and scan order executed inside transaction
    executed_sql = [q[0] for q in mock_conn.executed_queries]
    assert any("SET LOCAL app.current_tenant_id" in sql for sql in executed_sql)
    assert any(
        "SET LOCAL hnsw.iterative_scan = relaxed_order" in sql for sql in executed_sql
    )

    # Verify RRF scoring:
    # Item B appeared in both (#2 dense, #1 sparse): RRF = 1/(60+2) + 1/(60+1) = 0.016129 + 0.016393 = 0.032522
    # Item A appeared in dense (#1 dense, #9999 sparse): RRF = 1/(60+1) + 1/(60+9999) = 0.016393 + 0.000099 = 0.016492
    # Item C appeared in sparse (#9999 dense, #2 sparse): RRF = 0.000099 + 1/(60+2) = 0.016228
    assert len(results) == 3
    # Item B has highest RRF base and should be returned right at top after rerank
    item_b = next(r for r in results if r.memory_id == "item-b")
    assert item_b.dense_rank == 2
    assert item_b.sparse_rank == 1
    assert item_b.rrf_score > 0.032
