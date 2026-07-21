"""
Hybrid Retrieval Engine combining dense HNSW vector search, sparse full-text BM25,
Reciprocal Rank Fusion (RRF), and cross-encoder reranking (`services/memory-service/retrieval.py`).
Implements: PRD §4, SD §3.2, and implementation_plan.md §4B.
Enforces RLS (`SET LOCAL app.current_tenant_id = $1`) on every retrieval query.
"""

from __future__ import annotations

import json

import asyncpg

from memory_service.abstractions import (
    EmbeddingClient,
    HybridRetrievalQuery,
    RerankerClient,
    ScoredMemoryItem,
)
from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient


class HybridRetrievalEngine:
    """
    Production Multi-Hybrid RAG Retrieval Engine:
    1. Executes dense HNSW approximate nearest neighbors (`vector_cosine_ops`).
    2. Executes sparse full-text / BM25 keyword matching (`plainto_tsquery`).
    3. Merges candidate lists using Reciprocal Rank Fusion (`RRF`).
    4. Applies cross-encoder reranking over top candidates to produce final top_k.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        embedding_client: EmbeddingClient | None = None,
        reranker_client: RerankerClient | None = None,
    ) -> None:
        self._pool = pool
        self.embedding_client = embedding_client or MockEmbeddingClient()
        self.reranker_client = reranker_client or MockRerankerClient()

    async def retrieve_hybrid(
        self, query: HybridRetrievalQuery
    ) -> list[ScoredMemoryItem]:
        """Execute dense + sparse retrieval, RRF fusion, and cross-encoder reranking inside an RLS transaction."""
        embedding_str = "[" + ",".join(str(f) for f in query.query_embedding) + "]"

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. Enforce RLS and relaxed scan order per SD §7.1
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(query.tenant_id)
                )
                await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")

                # 2. Dense HNSW Retrieval (Top N candidates)
                dense_rows = await conn.fetch(
                    """
                    SELECT
                        id, tenant_id, learner_id, content, metadata, created_at,
                        1 - (embedding <=> $1::vector) AS dense_score
                    FROM learner_memories
                    WHERE learner_id = $2
                      AND expires_at > NOW()
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                    """,
                    embedding_str,
                    query.learner_id,
                    query.candidate_limit,
                )

                # 3. Sparse Full-Text / BM25 Retrieval (Top N candidates)
                sparse_rows = await conn.fetch(
                    """
                    SELECT
                        id, tenant_id, learner_id, content, metadata, created_at,
                        ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', $1)) AS sparse_score
                    FROM learner_memories
                    WHERE learner_id = $2
                      AND expires_at > NOW()
                      AND to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                    ORDER BY sparse_score DESC
                    LIMIT $3
                    """,
                    query.query_text,
                    query.learner_id,
                    query.candidate_limit,
                )

        # 4. Map candidates and assign independent dense & sparse ranks
        candidates: dict[str, ScoredMemoryItem] = {}

        for rank, row in enumerate(dense_rows, start=1):
            row_id = str(row["id"])
            meta = (
                json.loads(row["metadata"])
                if isinstance(row["metadata"], str)
                else (row["metadata"] or {})
            )
            candidates[row_id] = ScoredMemoryItem(
                memory_id=row_id,
                tenant_id=row["tenant_id"],
                learner_id=row["learner_id"],
                content=row["content"],
                dense_score=float(row["dense_score"]),
                dense_rank=rank,
                metadata=meta,
                created_at=row["created_at"],
            )

        for rank, row in enumerate(sparse_rows, start=1):
            row_id = str(row["id"])
            if row_id in candidates:
                candidates[row_id].sparse_score = float(row["sparse_score"])
                candidates[row_id].sparse_rank = rank
            else:
                meta = (
                    json.loads(row["metadata"])
                    if isinstance(row["metadata"], str)
                    else (row["metadata"] or {})
                )
                candidates[row_id] = ScoredMemoryItem(
                    memory_id=row_id,
                    tenant_id=row["tenant_id"],
                    learner_id=row["learner_id"],
                    content=row["content"],
                    sparse_score=float(row["sparse_score"]),
                    sparse_rank=rank,
                    metadata=meta,
                    created_at=row["created_at"],
                )

        # 5. Compute Reciprocal Rank Fusion (RRF) scores
        candidate_list = list(candidates.values())
        k = query.rrf_k
        for item in candidate_list:
            dense_part = query.dense_weight / (k + item.dense_rank)
            sparse_part = query.sparse_weight / (k + item.sparse_rank)
            item.rrf_score = round(dense_part + sparse_part, 6)

        # Sort descending by RRF score and retain top candidate_limit before reranking
        candidate_list.sort(key=lambda x: x.rrf_score, reverse=True)
        top_rrf = candidate_list[: query.candidate_limit]

        # 6. Cross-Encoder Reranking
        reranked = await self.reranker_client.rerank(
            query.query_text, top_rrf, top_k=query.top_k
        )
        return reranked
