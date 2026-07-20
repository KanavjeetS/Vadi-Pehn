"""
Contextual Retrieval Service managing session recency window, learner interest profiles,
and rapport-gated career panel introductions (`services/memory-service/context.py`).
Implements: PRD §4.3 (Rapport-gated career panel introductions), SD §3.2, and implementation_plan.md §4C.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from memory_service.abstractions import (
    ContextualTurnSummary,
    HybridRetrievalQuery,
    ScoredMemoryItem,
)
from memory_service.retrieval import HybridRetrievalEngine


class ContextualRetrievalService:
    """
    Orchestrates contextual retrieval for a conversation turn:
    1. Fetches hybrid RAG memories (dense + sparse + RRF + reranked).
    2. Fetches recent session dialogue turns (`session_history`) for recency context.
    3. Fetches learner rapport score and checks if `rapport_score >= rapport_threshold` (`70.0`).
    4. If rapport threshold is met, queries `learner_interest_profile` and retrieves matching
       `professional_personas` (`PRD §4.3`). If below threshold, blocks career panel introductions
       to prioritize virtual sibling emotional connection and rapport building.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        retrieval_engine: HybridRetrievalEngine,
        rapport_threshold: float = 70.0,
    ) -> None:
        self._pool = pool
        self.retrieval_engine = retrieval_engine
        self.rapport_threshold = rapport_threshold

    async def get_contextual_summary(
        self,
        query: HybridRetrievalQuery,
        session_window_size: int = 6,
        revoked_consent_categories: list[str] | None = None,
    ) -> ContextualTurnSummary:
        """
        Build full contextual summary including RAG items, session window, and rapport-gated panel.
        Strictly filters out memory items tagged with revoked consent categories per PRD §3.4/§3.5.
        """
        # 1. Execute Multi-Hybrid RAG Retrieval
        raw_memories = await self.retrieval_engine.retrieve_hybrid(query)

        # Apply PRD §3.4/§3.5 Consent Ledger Filtering
        revoked_set = set(revoked_consent_categories or [])
        retrieved_memories: list[ScoredMemoryItem] = []
        for mem in raw_memories:
            meta = mem.metadata if isinstance(mem.metadata, dict) else {}
            item_consent = meta.get("consent_category") or meta.get("consent_type")
            if item_consent and item_consent in revoked_set:
                # Exclude memory item belonging to revoked consent category!
                continue
            retrieved_memories.append(mem)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Enforce RLS for all context queries
                await conn.execute("SET LOCAL app.current_tenant_id = $1", str(query.tenant_id))

                # 2. Fetch recent session dialogue turns
                session_history: list[dict[str, str]] = []
                if query.session_id:
                    rows = await conn.fetch(
                        """
                        SELECT content, metadata
                        FROM learner_memories
                        WHERE learner_id = $1
                          AND conversation_session_id = $2
                          AND expires_at > NOW()
                        ORDER BY created_at DESC
                        LIMIT $3
                        """,
                        query.learner_id,
                        query.session_id,
                        session_window_size,
                    )
                    for row in reversed(rows):
                        meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
                        role = meta.get("role", "user")
                        session_history.append({"role": role, "content": row["content"]})

                # 3. Fetch learner rapport score
                rapport_val = await conn.fetchval(
                    """
                    SELECT rapport_score FROM learners
                    WHERE id = $1 AND tenant_id = $2
                    """,
                    query.learner_id,
                    query.tenant_id,
                )
                rapport_score = float(rapport_val) if rapport_val is not None else 0.0

                # 4. Rapport Gating check for Career Panel introductions (PRD §4.3)
                matched_personas: list[dict[str, Any]] = []
                panel_introduced = False

                if rapport_score >= self.rapport_threshold:
                    # Fetch interest profile topics
                    interest_rows = await conn.fetch(
                        """
                        SELECT topics FROM learner_interest_profile
                        WHERE learner_id = $1 AND tenant_id = $2
                        """,
                        query.learner_id,
                        query.tenant_id,
                    )
                    topics: set[str] = set()
                    for idx_row in interest_rows:
                        t_list = idx_row["topics"]
                        if isinstance(t_list, list):
                            topics.update(t_list)
                        elif isinstance(t_list, str):
                            try:
                                parsed = json.loads(t_list)
                                if isinstance(parsed, list):
                                    topics.update(parsed)
                            except Exception:
                                topics.add(t_list)

                    if topics:
                        persona_rows = await conn.fetch(
                            """
                            SELECT id, persona_name, career_domain, bio
                            FROM professional_personas
                            WHERE tenant_id = $1
                              AND career_domain = ANY($2::text[])
                            LIMIT 3
                            """,
                            query.tenant_id,
                            list(topics),
                        )
                        for prow in persona_rows:
                            matched_personas.append({
                                "id": str(prow["id"]),
                                "persona_name": prow["persona_name"],
                                "career_domain": prow["career_domain"],
                                "bio": prow["bio"],
                            })
                        if matched_personas:
                            panel_introduced = True

        return ContextualTurnSummary(
            session_history=session_history,
            retrieved_memories=retrieved_memories,
            rapport_score=rapport_score,
            matched_personas=matched_personas,
            panel_introduced=panel_introduced,
        )
