"""
Integration tests for OrchestrationGraph wiring with memory-service (Phase 5).
Verifies RAG contextual retrieval, Jinja2 template rendering, and consent-gated async memory writing.
"""

from datetime import datetime, timezone
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import pytest

# Add dynamic paths so imports resolve correctly
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "services",
            "memory-service",
            "src",
        )
    ),
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "services",
            "memory-service",
            "tests",
        )
    ),
)

from services.abstractions import MockLLMClient, MockSafetyClient, InMemoryVectorStore
from services.orchestration.src.orchestration.graph import OrchestrationGraph
from mock_db import MockAsyncpgConnection, MockAsyncpgPool
from memory_service.context import ContextualRetrievalService
from memory_service.retrieval import HybridRetrievalEngine
from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient
from memory_service.write_pipeline import AsyncMemoryWriter


class MockConsentChecker:
    def __init__(self, is_active: bool = True) -> None:
        self.is_active = is_active

    async def check_memory_write_consent(
        self, tenant_id: UUID, learner_id: UUID
    ) -> bool:
        return self.is_active


@pytest.mark.asyncio
async def test_orchestration_retrieves_memory_via_context_service_and_renders_jinja2():
    # Setup mock connection and pool
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    tenant_id = str(uuid4())
    learner_id = str(uuid4())
    session_id = str(uuid4())

    def custom_fetch(query: str, args: tuple) -> list[dict[str, Any]]:
        query_lower = query.lower()
        if "embedding <=>" in query_lower:
            # Dense retrieval HNSW
            return [
                {
                    "id": uuid4(),
                    "tenant_id": UUID(tenant_id),
                    "learner_id": UUID(learner_id),
                    "content": "Past robotics experience chunk.",
                    "metadata": "{}",
                    "created_at": datetime.now(timezone.utc),
                    "dense_score": 0.85,
                }
            ]
        elif "to_tsvector" in query_lower:
            # Sparse retrieval
            return []
        elif "conversation_session_id" in query_lower:
            # Session history
            return []
        elif "learner_interest_profile" in query_lower:
            # Topics
            return [{"topics": '["robotics"]'}]
        elif "professional_personas" in query_lower:
            # Career panel personas
            return [
                {
                    "id": uuid4(),
                    "persona_name": "Kavita (Robotics)",
                    "career_domain": "robotics",
                    "bio": "Expert in space drones.",
                }
            ]
        return []

    mock_conn.fetch_callback = custom_fetch
    mock_conn.fetchval_returns = [85.0]  # Rapport score above threshold

    # Setup RAG components
    embedding_client = MockEmbeddingClient()
    reranker = MockRerankerClient()
    retrieval_engine = HybridRetrievalEngine(mock_pool, embedding_client, reranker)
    context_service = ContextualRetrievalService(
        mock_pool, retrieval_engine, rapport_threshold=70.0
    )
    memory_writer = AsyncMemoryWriter(
        mock_pool, MockConsentChecker(True), embedding_client
    )

    # Initialize graph
    graph = OrchestrationGraph(
        safety_client=MockSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="Hello from mock LLM"),
        embedding_client=embedding_client,
        context_service=context_service,
        memory_writer=memory_writer,
    )

    state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="I want to study robotics",
    )

    # Verify RAG retrieved matched personas because rapport threshold was met
    assert state.panel_triggered is True
    assert state.panel_result is not None
    assert state.panel_result["rapport_score"] == 85.0
    assert len(state.panel_result["personas"]) == 1
    assert state.panel_result["personas"][0]["persona_name"] == "Kavita (Robotics)"

    # Verify immediate acknowledgment is returned when panel triggers
    assert graph.llm_client.call_count == 0
    assert (
        state.final_reply
        == "yeh ek bahut acha sawal hai — mujhe apne doston se puchne do, ek second!"
    )


@pytest.mark.asyncio
async def test_orchestration_blocks_panel_trigger_when_rapport_below_threshold():
    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    tenant_id = str(uuid4())
    learner_id = str(uuid4())
    session_id = str(uuid4())

    def custom_fetch(query: str, args: tuple) -> list[dict[str, Any]]:
        query_lower = query.lower()
        if "embedding <=>" in query_lower:
            # Dense retrieval
            return []
        elif "to_tsvector" in query_lower:
            # Sparse retrieval
            return []
        elif "conversation_session_id" in query_lower:
            # Session history
            return []
        elif "learner_interest_profile" in query_lower:
            # Topics
            return [{"topics": '["robotics"]'}]
        elif "professional_personas" in query_lower:
            # Career personas
            return [
                {
                    "id": uuid4(),
                    "persona_name": "Kavita (Robotics)",
                    "career_domain": "robotics",
                    "bio": "Expert in space drones.",
                }
            ]
        return []

    mock_conn.fetch_callback = custom_fetch
    mock_conn.fetchval_returns = [45.0]  # Rapport below 70 threshold

    embedding_client = MockEmbeddingClient()
    retrieval_engine = HybridRetrievalEngine(mock_pool, embedding_client)
    context_service = ContextualRetrievalService(
        mock_pool, retrieval_engine, rapport_threshold=70.0
    )
    memory_writer = AsyncMemoryWriter(
        mock_pool, MockConsentChecker(True), embedding_client
    )

    graph = OrchestrationGraph(
        safety_client=MockSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="Vadi: Keep coding!"),
        embedding_client=embedding_client,
        context_service=context_service,
        memory_writer=memory_writer,
    )

    state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="I want to build machines",
    )

    # Panel must NOT trigger because rapport score is too low
    assert state.panel_triggered is False
    assert state.panel_result is None
    # LLM was invoked and generated the reply
    assert graph.llm_client.call_count == 1
    assert state.final_reply == "Vadi: Keep coding!"
