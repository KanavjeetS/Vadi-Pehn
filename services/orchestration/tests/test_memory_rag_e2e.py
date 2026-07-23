"""
End-to-End Integration Tests for Multi-Turn Conversation Memory RAG & Consent Enforcement.
Implements Milestone 6 (Requirement R6): PRD & SystemDesign Compliance.

Verifies:
  1. Turn 1 (Memory Storage): Disclosing key interest ("My favorite hobby is astronomy and I want to study galaxies")
     stores memory embedding record in the memory vector store via write_memory.
  2. Turn 2 (Memory Retrieval & Contextual Recall): Follow-up ("Do you remember what hobby I told you about?")
     retrieves Turn 1 memory via retrieve_memory / ContextualRetrievalService, injects into prompt context,
     and produces AI reply referencing astronomy and galaxies.
  3. Consent Boundary: Honors conversation_storage toggle in Governance Service (skips writing / filters revoked memory).
  4. RLS Tenant Isolation: Memory store queries enforce tenant_id scoping.
  5. FastAPI Boundary: POST /internal/v1/orchestration/turn returns 200 with valid TurnState response.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
import uuid
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

# Ensure internal modules resolve
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ORCH_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
MEM_SRC = os.path.abspath(os.path.join(ROOT_DIR, "services", "memory-service", "src"))
MEM_TESTS = os.path.abspath(os.path.join(ROOT_DIR, "services", "memory-service", "tests"))

for path in (ROOT_DIR, ORCH_SRC, MEM_SRC, MEM_TESTS):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.abstractions import (  # noqa: E402
    InMemoryVectorStore,
    LLMClient,
    MockLLMClient,
    MockSafetyClient,
    SafetyVerdictCode,
)
from services.orchestration.src.orchestration.graph import (  # noqa: E402
    OrchestrationGraph,
)
import services.orchestration.src.orchestration.main as orchestration_main  # noqa: E402
from services.orchestration.src.orchestration.main import app  # noqa: E402


class DynamicAstronomyLLMClient(LLMClient):
    """
    LLM Client mock that simulates memory awareness.
    If system prompt contains astronomy context, reply explicitly references astronomy/galaxies.
    """

    def __init__(self) -> None:
        self.call_history: list[list[dict[str, str]]] = []

    async def generate(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str | list[str]:
        self.call_history.append(messages)
        system_prompt = messages[0]["content"] if messages else ""
        user_message = messages[1]["content"] if len(messages) > 1 else ""

        # Turn 1 initial response
        if "astronomy" in user_message.lower() or "galaxies" in user_message.lower():
            reply = "Astronomy and studying galaxies is amazing! I will remember that you love astronomy."
        # Turn 2 recall response when memory context is present in system prompt
        elif "astronomy" in system_prompt.lower() or "galaxies" in system_prompt.lower():
            reply = "Yes! I remember you told me your favorite hobby is astronomy and you want to study galaxies!"
        else:
            reply = "I am your sibling mentor! What would you like to talk about today?"

        if stream:
            return [reply]
        return reply


@pytest.mark.asyncio
async def test_memory_rag_e2e_storage_and_contextual_recall():
    """
    E2E Multi-Turn Test:
      Turn 1: Learner discloses hobby ("My favorite hobby is astronomy and I want to study galaxies").
              Assert write_memory persists the memory chunk.
      Turn 2: Learner asks ("Do you remember what hobby I told you about?").
              Assert retrieve_memory retrieves astronomy memory chunk, injects into prompt,
              and response explicitly references astronomy & galaxies.
    """
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    memory_store = InMemoryVectorStore()
    llm_client = DynamicAstronomyLLMClient()
    safety_client = MockSafetyClient()

    graph = OrchestrationGraph(
        safety_client=safety_client,
        memory_store=memory_store,
        llm_client=llm_client,
    )

    # ── Turn 1: Disclose astronomy interest ──
    turn1_state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="My favorite hobby is astronomy and I want to study galaxies",
    )

    # Assert Turn 1 response and state
    assert turn1_state.final_reply != ""
    assert turn1_state.safety_verdict_input["code"] == SafetyVerdictCode.SAFE.value
    assert turn1_state.safety_verdict_output["code"] == SafetyVerdictCode.SAFE.value
    assert "astronomy" in turn1_state.final_reply.lower()

    # Assert write_memory persisted memory chunk in memory_store
    stored_chunks = await memory_store.query(
        tenant_id=UUID(tenant_id),
        learner_id=UUID(learner_id),
        query_embedding=[0.0] * 1536,
        k=5,
    )
    assert len(stored_chunks) > 0
    assert "astronomy" in stored_chunks[0].content.lower()

    # ── Turn 2: Follow-up question ──
    turn2_state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="Do you remember what hobby I told you about?",
    )

    # Assert retrieve_memory fetched memory from Turn 1
    assert len(turn2_state.memory_context) > 0
    assert any("astronomy" in item["content"].lower() for item in turn2_state.memory_context)

    # Assert Turn 2 response explicitly recalls astronomy & galaxies
    assert "astronomy" in turn2_state.final_reply.lower()
    assert "galaxies" in turn2_state.final_reply.lower()


@pytest.mark.asyncio
async def test_memory_rag_e2e_hybrid_rag_pipeline():
    """
    Verifies full integration between OrchestrationGraph, ContextualRetrievalService,
    HybridRetrievalEngine, and AsyncMemoryWriter.
    """
    from memory_service.context import ContextualRetrievalService
    from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient
    from memory_service.retrieval import HybridRetrievalEngine
    from memory_service.write_pipeline import AsyncMemoryWriter
    from mock_db import MockAsyncpgConnection, MockAsyncpgPool

    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)

    def custom_fetch(query: str, args: tuple) -> list[dict[str, Any]]:
        query_lower = query.lower()
        if "embedding <=>" in query_lower:
            return [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": UUID(tenant_id),
                    "learner_id": UUID(learner_id),
                    "content": "Learner disclosed interest: My favorite hobby is astronomy and I want to study galaxies",
                    "metadata": "{}",
                    "created_at": datetime.now(timezone.utc),
                    "dense_score": 0.92,
                }
            ]
        elif "conversation_session_id" in query_lower:
            return [
                {
                    "content": "My favorite hobby is astronomy and I want to study galaxies",
                    "metadata": '{"role": "user"}',
                }
            ]
        elif "learner_interest_profile" in query_lower:
            return [{"topics": '["astronomy"]'}]
        elif "professional_personas" in query_lower:
            return [
                {
                    "id": uuid.uuid4(),
                    "persona_name": "Dr. Sarah (Astrophysicist)",
                    "career_domain": "astronomy",
                    "bio": "Astrophysicist studying space telescopes.",
                }
            ]
        return []

    mock_conn.fetch_callback = custom_fetch
    mock_conn.fetchval_returns = [80.0]  # Rapport score above threshold (80.0 >= 70.0)

    embedding_client = MockEmbeddingClient()
    reranker = MockRerankerClient()
    retrieval_engine = HybridRetrievalEngine(mock_pool, embedding_client, reranker)
    context_service = ContextualRetrievalService(
        mock_pool, retrieval_engine, rapport_threshold=70.0
    )

    class MockConsentChecker:
        async def check_memory_write_consent(self, tenant_id: UUID, learner_id: UUID) -> bool:
            return True

    memory_writer = AsyncMemoryWriter(mock_pool, MockConsentChecker(), embedding_client)
    llm_client = DynamicAstronomyLLMClient()

    graph = OrchestrationGraph(
        safety_client=MockSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=llm_client,
        embedding_client=embedding_client,
        context_service=context_service,
        memory_writer=memory_writer,
    )

    turn_state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="What is my hobby?",
    )

    assert len(turn_state.memory_context) > 0
    assert "astronomy" in turn_state.memory_context[0]["content"].lower()


@pytest.mark.asyncio
async def test_memory_storage_governance_consent_check():
    """
    Verify memory storage honors conversation_storage consent toggle.
    When conversation_storage is active, write_memory persists memory.
    When conversation_storage is inactive/disabled, write_memory is skipped or raises consent error.
    """
    from memory_service.abstractions import ConsentCheckerClient
    from memory_service.embeddings import MockEmbeddingClient
    from memory_service.write_pipeline import AsyncMemoryWriter, ConsentDeniedWriteAbort
    from mock_db import MockAsyncpgConnection, MockAsyncpgPool

    class ToggleableConsentChecker(ConsentCheckerClient):
        def __init__(self, allowed: bool = True):
            self.allowed = allowed

        async def check_memory_write_consent(self, tenant_id: UUID, learner_id: UUID) -> bool:
            return self.allowed

    tenant_id = UUID(str(uuid.uuid4()))
    learner_id = UUID(str(uuid.uuid4()))
    session_id = UUID(str(uuid.uuid4()))

    mock_conn = MockAsyncpgConnection()
    mock_pool = MockAsyncpgPool(mock_conn)
    embedding_client = MockEmbeddingClient()

    # 1. Active consent: write succeeds
    active_consent = ToggleableConsentChecker(allowed=True)
    writer_active = AsyncMemoryWriter(mock_pool, active_consent, embedding_client)
    written_ids = await writer_active.write_memory_chunked(
        tenant_id=tenant_id,
        learner_id=learner_id,
        content="Child: My favorite hobby is astronomy\nVadi: That is great!",
        session_id=session_id,
    )
    assert len(written_ids) > 0

    # 2. Inactive consent: write fails closed with ConsentDeniedWriteAbort
    inactive_consent = ToggleableConsentChecker(allowed=False)
    writer_inactive = AsyncMemoryWriter(mock_pool, inactive_consent, embedding_client)
    with pytest.raises(ConsentDeniedWriteAbort, match="No active consent"):
        await writer_inactive.write_memory_chunked(
            tenant_id=tenant_id,
            learner_id=learner_id,
            content="Child: My favorite hobby is astronomy\nVadi: That is great!",
            session_id=session_id,
        )


@pytest.mark.asyncio
async def test_consent_boundary_revoked_category_filtering():
    """
    Verify ContextualRetrievalService filters out memory items when consent category is revoked per PRD §3.4.
    """
    from memory_service.abstractions import HybridRetrievalQuery, ScoredMemoryItem
    from memory_service.context import ContextualRetrievalService
    from memory_service.embeddings import MockEmbeddingClient
    from memory_service.retrieval import HybridRetrievalEngine
    from mock_db import MockAsyncpgConnection, MockAsyncpgPool

    mock_conn = MockAsyncpgConnection()
    mock_conn.fetchval_returns = [0.0]  # Low rapport score -> skips career panel queries
    mock_pool = MockAsyncpgPool(mock_conn)
    embedding_client = MockEmbeddingClient()
    tenant_id = uuid.uuid4()
    learner_id = uuid.uuid4()

    class CustomRetrievalEngine(HybridRetrievalEngine):
        async def retrieve_hybrid(self, query: HybridRetrievalQuery) -> list[ScoredMemoryItem]:
            return [
                ScoredMemoryItem(
                    memory_id=uuid.uuid4(),
                    tenant_id=query.tenant_id,
                    learner_id=query.learner_id,
                    content="Astronomy memory with revoked storage consent",
                    rrf_score=0.9,
                    metadata={"consent_category": "conversation_storage"},
                ),
                ScoredMemoryItem(
                    memory_id=uuid.uuid4(),
                    tenant_id=query.tenant_id,
                    learner_id=query.learner_id,
                    content="Allowed memory without revoked consent",
                    rrf_score=0.8,
                    metadata={"consent_category": "general"},
                ),
            ]

    engine = CustomRetrievalEngine(mock_pool, embedding_client)
    context_service = ContextualRetrievalService(mock_pool, engine)

    query = HybridRetrievalQuery(
        tenant_id=tenant_id,
        learner_id=learner_id,
        query_text="What is my hobby?",
        query_embedding=[0.1] * 1536,
    )

    # When conversation_storage consent is revoked:
    summary = await context_service.get_contextual_summary(
        query, revoked_consent_categories=["conversation_storage"]
    )

    # Assert revoked memory is excluded from retrieved_memories
    assert len(summary.retrieved_memories) == 1
    assert summary.retrieved_memories[0].content == "Allowed memory without revoked consent"


@pytest.mark.asyncio
async def test_rls_tenant_scoping_enforced_on_all_memory_operations():
    """
    CRITICAL GUARDRAIL G-002 Verification:
    Verify memory vector store queries strictly enforce tenant_id isolation.
    Tenant B cannot view memories stored by Tenant A for the same learner ID.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    learner_id = uuid.uuid4()

    memory_store = InMemoryVectorStore()

    # Write memory for Tenant A
    await memory_store.write(
        tenant_id=tenant_a,
        learner_id=learner_id,
        content="Tenant A confidential astronomy disclosure: astronomy and galaxies",
        embedding=[0.1] * 1536,
    )

    # Query with Tenant A -> returns memory
    chunks_a = await memory_store.query(
        tenant_id=tenant_a,
        learner_id=learner_id,
        query_embedding=[0.1] * 1536,
        k=5,
    )
    assert len(chunks_a) == 1
    assert "Tenant A" in chunks_a[0].content

    # Query with Tenant B -> returns 0 memories (strict RLS isolation)
    chunks_b = await memory_store.query(
        tenant_id=tenant_b,
        learner_id=learner_id,
        query_embedding=[0.1] * 1536,
        k=5,
    )
    assert len(chunks_b) == 0


def test_fastapi_orchestration_turn_endpoint():
    """
    Verifies POST /internal/v1/orchestration/turn HTTP API boundary with FastAPI TestClient.
    """
    with TestClient(app) as client:
        # Override safety_client and llm_client in test runtime to mock network safety proxy & LLM
        if orchestration_main.graph is not None:
            orchestration_main.graph.safety_client = MockSafetyClient()
            orchestration_main.graph.llm_client = MockLLMClient(
                reply="Hello! I am Vadi, your virtual sibling mentor."
            )

        payload = {
            "session_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "learner_id": str(uuid.uuid4()),
            "age_band": 2,
            "message_text": "Hello Vadi! How are you today?",
            "language": "en",
        }
        response = client.post(
            "/internal/v1/orchestration/turn",
            json=payload,
            headers={"X-Internal-Service-Token": ""},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == payload["session_id"]
        assert data["final_reply"] != ""
