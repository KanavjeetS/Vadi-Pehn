"""
Memory Retrieval module for Orchestration Service.
Implements: SD §3.2, PRD §4 (Memory Retrieval).
Enforces LIMIT 5 recency-based query fallback when vector embedding client is unavailable so context is always populated.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from services.abstractions import MemoryChunk, MemoryStore

logger = logging.getLogger("orchestration.retrieval")


class OrchestrationRetrieval:
    """
    Retrieval helper for OrchestrationGraph.
    Performs dense/sparse hybrid vector search when embedding_client and context_service are available.
    Falls back to LIMIT 5 recency-based memory_store query when embedding_client is unavailable or fails.
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        embedding_client: Any | None = None,
        context_service: Any | None = None,
    ) -> None:
        self.memory_store = memory_store
        self.embedding_client = embedding_client
        self.context_service = context_service

    async def retrieve_context(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        query_text: str,
        session_id: UUID | None = None,
        top_k: int = 5,
    ) -> tuple[list[dict[str, Any]], bool, dict[str, Any] | None]:
        """
        Retrieve memory context for a learner's turn.
        Returns:
            (memory_context_list, panel_introduced, panel_result)
        """
        # Primary path: Hybrid Vector Search via context_service & embedding_client
        if self.context_service and self.embedding_client:
            try:
                from memory_service.abstractions import HybridRetrievalQuery

                query_embedding = await self.embedding_client.embed_text(query_text)
                if query_embedding:
                    query = HybridRetrievalQuery(
                        tenant_id=tenant_id,
                        learner_id=learner_id,
                        query_text=query_text,
                        query_embedding=query_embedding,
                        session_id=session_id,
                        top_k=top_k,
                    )
                    summary = await self.context_service.get_contextual_summary(query)
                    memory_context = [
                        {"content": item.content, "chunk_id": str(item.memory_id)}
                        for item in summary.retrieved_memories
                    ]
                    panel_result = (
                        {
                            "personas": summary.matched_personas,
                            "rapport_score": summary.rapport_score,
                        }
                        if summary.panel_introduced
                        else None
                    )
                    return memory_context, summary.panel_introduced, panel_result
            except Exception as err:
                logger.warning(
                    f"Hybrid vector retrieval failed ({err}). Executing LIMIT {top_k} recency fallback."
                )

        # Fallback path: LIMIT top_k recency-based query when embedding client is unavailable or fails
        stub_embedding = [0.0] * 1536
        chunks: list[MemoryChunk] = await self.memory_store.query(
            tenant_id=tenant_id,
            learner_id=learner_id,
            query_embedding=stub_embedding,
            k=top_k,
        )
        memory_context = [
            {"content": c.content, "chunk_id": c.chunk_id} for c in chunks
        ]
        return memory_context, False, None
