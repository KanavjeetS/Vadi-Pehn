"""
Hybrid vs Pure Dense Retrieval Benchmark suite (`services/memory-service/benchmark.py`).
Implements: implementation_plan.md §4E Success Criteria.
Measures Recall@K across child domain queries to verify that Multi-Hybrid RAG
(Dense HNSW + Sparse BM25 + RRF + Reranking) outperforms pure vector similarity alone.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from memory_service.abstractions import HybridRetrievalQuery
from memory_service.retrieval import HybridRetrievalEngine


@dataclass
class BenchmarkQuerySpec:
    query_text: str
    expected_substrings: list[str]


@dataclass
class BenchmarkComparisonResult:
    total_queries: int
    dense_hits: int
    hybrid_hits: int
    dense_recall_at_k: float
    hybrid_recall_at_k: float
    hybrid_wins: bool


class HybridRetrievalBenchmark:
    """
    Executes comparison queries measuring Recall@K between Pure Dense vector retrieval
    and our Multi-Hybrid RAG engine over child tutoring and emotional rapport memories.
    """

    def __init__(self, pool: asyncpg.Pool, hybrid_engine: HybridRetrievalEngine) -> None:
        self._pool = pool
        self.hybrid_engine = hybrid_engine

    async def evaluate_benchmark(
        self,
        tenant_id: UUID,
        learner_id: UUID,
        queries: list[BenchmarkQuerySpec],
        top_k: int = 5,
    ) -> BenchmarkComparisonResult:
        if not queries:
            return BenchmarkComparisonResult(0, 0, 0, 0.0, 0.0, False)

        dense_hits = 0
        hybrid_hits = 0

        for qspec in queries:
            vec = await self.hybrid_engine.embedding_client.embed_text(qspec.query_text)

            # 1. Evaluate Pure Dense
            embedding_str = "[" + ",".join(str(f) for f in vec) + "]"
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))
                    await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                    dense_rows = await conn.fetch(
                        """
                        SELECT content FROM learner_memories
                        WHERE learner_id = $1 AND expires_at > NOW()
                        ORDER BY embedding <=> $2::vector
                        LIMIT $3
                        """,
                        learner_id,
                        embedding_str,
                        top_k,
                    )
            dense_contents = [r["content"] for r in dense_rows]
            dense_hit = any(
                all(sub.lower() in content.lower() for sub in qspec.expected_substrings)
                for content in dense_contents
            )
            if dense_hit:
                dense_hits += 1

            # 2. Evaluate Multi-Hybrid RAG
            hquery = HybridRetrievalQuery(
                tenant_id=tenant_id,
                learner_id=learner_id,
                query_text=qspec.query_text,
                query_embedding=vec,
                top_k=top_k,
                candidate_limit=20,
            )
            hybrid_items = await self.hybrid_engine.retrieve_hybrid(hquery)
            hybrid_contents = [item.content for item in hybrid_items]
            hybrid_hit = any(
                all(sub.lower() in content.lower() for sub in qspec.expected_substrings)
                for content in hybrid_contents
            )
            if hybrid_hit:
                hybrid_hits += 1

        total = len(queries)
        dense_recall = round(dense_hits / total, 4)
        hybrid_recall = round(hybrid_hits / total, 4)

        return BenchmarkComparisonResult(
            total_queries=total,
            dense_hits=dense_hits,
            hybrid_hits=hybrid_hits,
            dense_recall_at_k=dense_recall,
            hybrid_recall_at_k=hybrid_recall,
            hybrid_wins=(hybrid_recall >= dense_recall),
        )
