"""
Unit tests for HybridRetrievalBenchmark (`services/memory-service/tests/test_benchmark.py`).
Verifies that Multi-Hybrid RAG (Dense + Sparse BM25 + RRF + Cross-Encoder Rerank)
beats Pure Dense retrieval on child-domain exact keyword/entity recall.
"""

from datetime import datetime, timezone
from uuid import UUID
import json

import pytest

from mock_db import MockAsyncpgConnection, MockAsyncpgPool
from memory_service.benchmark import (
    BenchmarkComparisonResult,
    BenchmarkQuerySpec,
    HybridRetrievalBenchmark,
)
from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient
from memory_service.retrieval import HybridRetrievalEngine


@pytest.mark.asyncio
async def test_hybrid_benchmark_shows_recall_superiority_over_pure_dense():
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    learner_id = UUID("22222222-2222-2222-2222-222222222222")

    # For pure dense query: returns generic algebra memory (does NOT contain 'Sharma')
    dense_rows = [
        {"content": "General algebra equations tutoring notes."},
        {"content": "Learner likes science experiments."},
    ]

    # For hybrid retrieval: dense returns general, sparse returns exact Mr. Sharma keyword hit
    hybrid_dense_rows = [
        {
            "id": "1",
            "tenant_id": tenant_id,
            "learner_id": learner_id,
            "content": "General algebra equations tutoring notes.",
            "metadata": "{}",
            "created_at": datetime.now(timezone.utc),
            "dense_score": 0.85,
        }
    ]
    hybrid_sparse_rows = [
        {
            "id": "2",
            "tenant_id": tenant_id,
            "learner_id": learner_id,
            "content": "Learner mentioned science teacher Mr. Sharma helps with biology lab.",
            "metadata": "{}",
            "created_at": datetime.now(timezone.utc),
            "sparse_score": 1.2,
        }
    ]

    mock_conn.fetch_returns = [dense_rows, hybrid_dense_rows, hybrid_sparse_rows]

    engine = HybridRetrievalEngine(
        pool=mock_pool,
        embedding_client=MockEmbeddingClient(),
        reranker_client=MockRerankerClient(),
    )
    benchmark = HybridRetrievalBenchmark(pool=mock_pool, hybrid_engine=engine)

    queries = [
        BenchmarkQuerySpec(
            query_text="Who is Mr. Sharma?",
            expected_substrings=["Mr. Sharma", "biology"],
        )
    ]

    result = await benchmark.evaluate_benchmark(tenant_id, learner_id, queries, top_k=2)

    # Verify that pure dense missed exact entity, while hybrid RAG hit it
    assert result.total_queries == 1
    assert result.dense_hits == 0
    assert result.hybrid_hits == 1
    assert result.dense_recall_at_k == 0.0
    assert result.hybrid_recall_at_k == 1.0
    assert result.hybrid_wins is True


def test_benchmark_report_is_explicitly_labelled(tmp_path):
    result = BenchmarkComparisonResult(
        total_queries=1,
        dense_hits=0,
        hybrid_hits=1,
        dense_recall_at_k=0.0,
        hybrid_recall_at_k=1.0,
        hybrid_wins=True,
    )

    output = tmp_path / "memory_benchmark.json"
    HybridRetrievalBenchmark.write_report(result, output)
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["benchmark_type"] == "synthetic_eval"
    assert report["result"]["hybrid_recall_at_k"] == 1.0
