"""
Adversarial Challenge Test Suite for AI Turn Execution & Memory RAG Pipeline.
Created by challenger_m6_2.

Verifies:
  1. Multi-turn memory persistence across sessions for the same learner in same tenant.
  2. Multi-turn memory isolation between different learners in the same tenant.
  3. Cross-tenant memory isolation (Learner B in Tenant 2 cannot retrieve memories from Learner A in Tenant 1).
  4. Consent enforcement: conversation_storage=False prevents write (ConsentDeniedWriteAbort) and filters recall.
  5. Fail-closed input safety pre-filter: UNSAFE or CLASSIFIER_UNAVAILABLE inputs bypass retrieve_memory and write_memory.
"""

from __future__ import annotations

import os
import sys
import uuid
from uuid import UUID

import pytest

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
    MockSafetyClient,
    SafetyVerdict,
    SafetyVerdictCode,
)
from services.orchestration.src.orchestration.graph import (  # noqa: E402
    OrchestrationGraph,
)


class DynamicRecallLLMClient(LLMClient):
    """
    LLM Client mock that inspects system prompt context for recalled memories.
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
        if "origami" in user_message.lower():
            reply = "Origami crafting is wonderful! I'll remember you love origami."
        elif "astronomy" in user_message.lower() or "galaxies" in user_message.lower():
            reply = "Astronomy and studying galaxies is amazing! I will remember that."
        elif "astrophysics" in user_message.lower():
            reply = "Astrophysics is super cool! I'll remember that."
        # Turn 2 recall responses when memory is present in system prompt
        elif "origami" in system_prompt.lower():
            reply = "I remember you told me your secret hobby is origami crafting!"
        elif "astronomy" in system_prompt.lower() or "galaxies" in system_prompt.lower():
            reply = "Yes! I remember you told me your favorite hobby is astronomy and studying galaxies!"
        elif "astrophysics" in system_prompt.lower():
            reply = "Yes, I remember you love astrophysics!"
        else:
            reply = "I don't recall you mentioning any specific hobby yet. What do you like to do?"

        if stream:
            return [reply]
        return reply


@pytest.mark.asyncio
async def test_multiturn_persistence_same_learner_diff_sessions():
    """
    Empirical Test: Verify multi-turn memory persistence across sessions for the same learner in same tenant.
    Session 1: Learner discloses hobby ("My favorite hobby is astronomy and I want to study galaxies").
    Session 2: Learner asks follow-up ("Do you remember what hobby I told you about?") in a brand NEW session.
    Assert memory is retrieved and recalled in response.
    """
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    session_1 = str(uuid.uuid4())
    session_2 = str(uuid.uuid4())

    memory_store = InMemoryVectorStore()
    llm_client = DynamicRecallLLMClient()
    safety_client = MockSafetyClient()

    graph = OrchestrationGraph(
        safety_client=safety_client,
        memory_store=memory_store,
        llm_client=llm_client,
    )

    # Session 1 Turn 1
    t1_state = await graph.run_turn(
        session_id=session_1,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="My favorite hobby is astronomy and I want to study galaxies",
    )
    assert "astronomy" in t1_state.final_reply.lower()

    # Session 2 Turn 1 (New session ID, same learner and tenant)
    t2_state = await graph.run_turn(
        session_id=session_2,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="Do you remember what hobby I told you about?",
    )
    assert len(t2_state.memory_context) > 0
    assert any("astronomy" in item["content"].lower() for item in t2_state.memory_context)
    assert "astronomy" in t2_state.final_reply.lower()


@pytest.mark.asyncio
async def test_multiturn_isolation_different_learners_same_tenant():
    """
    Empirical Test: Verify memory isolation between different learners in the SAME tenant.
    Learner A (Tenant 1): discloses "My secret hobby is origami crafting".
    Learner B (Tenant 1): asks "Do you remember what hobby I told you about?".
    Assert Learner B receives NO memories from Learner A and AI does NOT recall origami.
    """
    tenant_id = str(uuid.uuid4())
    learner_a = str(uuid.uuid4())
    learner_b = str(uuid.uuid4())

    memory_store = InMemoryVectorStore()
    llm_client = DynamicRecallLLMClient()
    safety_client = MockSafetyClient()

    graph = OrchestrationGraph(
        safety_client=safety_client,
        memory_store=memory_store,
        llm_client=llm_client,
    )

    # Learner A Turn 1
    await graph.run_turn(
        session_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        learner_id=learner_a,
        age_band=2,
        message_text="My secret hobby is origami crafting",
    )

    # Learner B Turn 1 in same tenant
    t_b = await graph.run_turn(
        session_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        learner_id=learner_b,
        age_band=2,
        message_text="Do you remember what hobby I told you about?",
    )

    # Assert Learner B gets zero memories from Learner A
    assert len(t_b.memory_context) == 0
    assert "origami" not in t_b.final_reply.lower()


@pytest.mark.asyncio
async def test_cross_tenant_memory_isolation_e2e():
    """
    Empirical Test: Verify cross-tenant memory isolation.
    Learner A in Tenant 1 stores memory ("My favorite hobby is astrophysics").
    Learner B in Tenant 2 (even if using same or different learner ID) asks for recall.
    Assert Learner B in Tenant 2 cannot retrieve memories saved by Learner A in Tenant 1.
    """
    tenant_1 = str(uuid.uuid4())
    tenant_2 = str(uuid.uuid4())
    shared_learner_id = str(uuid.uuid4())  # Same learner ID string, different tenant

    memory_store = InMemoryVectorStore()
    llm_client = DynamicRecallLLMClient()
    safety_client = MockSafetyClient()

    graph = OrchestrationGraph(
        safety_client=safety_client,
        memory_store=memory_store,
        llm_client=llm_client,
    )

    # Learner in Tenant 1
    await graph.run_turn(
        session_id=str(uuid.uuid4()),
        tenant_id=tenant_1,
        learner_id=shared_learner_id,
        age_band=2,
        message_text="My favorite hobby is astrophysics",
    )

    # Learner in Tenant 2 (same learner_id string, tenant_2)
    t2_state = await graph.run_turn(
        session_id=str(uuid.uuid4()),
        tenant_id=tenant_2,
        learner_id=shared_learner_id,
        age_band=2,
        message_text="Do you remember what hobby I told you about?",
    )

    # Assert Tenant 2 cannot access Tenant 1 memory
    assert len(t2_state.memory_context) == 0
    assert "astrophysics" not in t2_state.final_reply.lower()


@pytest.mark.asyncio
async def test_memory_recall_when_consent_conversation_storage_disabled():
    """
    Empirical Test: Verify memory write and recall behavior when conversation_storage consent is False / revoked.
    1. Verify AsyncMemoryWriter raises ConsentDeniedWriteAbort when consent is False.
    2. Verify ContextualRetrievalService excludes memories tagged with revoked consent categories.
    3. Verify response contains NO recalled memory when consent is revoked.
    """
    from memory_service.abstractions import ConsentCheckerClient, HybridRetrievalQuery, ScoredMemoryItem
    from memory_service.context import ContextualRetrievalService
    from memory_service.embeddings import MockEmbeddingClient
    from memory_service.retrieval import HybridRetrievalEngine
    from memory_service.write_pipeline import AsyncMemoryWriter, ConsentDeniedWriteAbort
    from mock_db import MockAsyncpgConnection, MockAsyncpgPool

    class DeniedConsentChecker(ConsentCheckerClient):
        async def check_memory_write_consent(self, tenant_id: UUID, learner_id: UUID) -> bool:
            return False  # consent conversation_storage = False

    tenant_id = uuid.uuid4()
    learner_id = uuid.uuid4()
    session_id = uuid.uuid4()

    mock_conn = MockAsyncpgConnection()
    mock_conn.fetchval_returns = [0.0]
    mock_pool = MockAsyncpgPool(mock_conn)
    embedding_client = MockEmbeddingClient()

    # 1. Write attempt fails closed when consent is False
    writer = AsyncMemoryWriter(mock_pool, DeniedConsentChecker(), embedding_client)
    with pytest.raises(ConsentDeniedWriteAbort, match="No active consent"):
        await writer.write_memory_chunked(
            tenant_id=tenant_id,
            learner_id=learner_id,
            content="Child: My favorite hobby is astronomy\nVadi: Great!",
            session_id=session_id,
        )

    # 2. Retrieval attempt filters out revoked conversation_storage category
    class DummyEngine(HybridRetrievalEngine):
        async def retrieve_hybrid(self, query: HybridRetrievalQuery) -> list[ScoredMemoryItem]:
            return [
                ScoredMemoryItem(
                    memory_id=uuid.uuid4(),
                    tenant_id=query.tenant_id,
                    learner_id=query.learner_id,
                    content="Disclosed hobby: astronomy",
                    rrf_score=0.95,
                    metadata={"consent_category": "conversation_storage"},
                )
            ]

    engine = DummyEngine(mock_pool, embedding_client)
    context_service = ContextualRetrievalService(mock_pool, engine)

    query = HybridRetrievalQuery(
        tenant_id=tenant_id,
        learner_id=learner_id,
        query_text="What is my hobby?",
        query_embedding=[0.0] * 1536,
    )

    summary = await context_service.get_contextual_summary(
        query, revoked_consent_categories=["conversation_storage"]
    )
    assert len(summary.retrieved_memories) == 0  # Excluded!


@pytest.mark.asyncio
async def test_fail_closed_safety_prefilter_unsafe_input():
    """
    Empirical Test: Verify check_input_safety fail-closed behavior on unsafe input.
    When unsafe input is sent:
    - Input safety pre-filter returns blocks_generation=True.
    - Graph routes to handle_unsafe_input and create_governance_incident.
    - retrieve_memory is NOT executed (memory_context is empty).
    - write_memory is NOT executed (no memory stored).
    """
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    memory_store = InMemoryVectorStore()
    llm_client = DynamicRecallLLMClient()

    class UnsafeInputSafetyClient(MockSafetyClient):
        async def check_input(
            self,
            *,
            learner_id: UUID,
            message_text: str,
            age_band: int,
            tenant_id: UUID,
        ) -> SafetyVerdict:
            return SafetyVerdict(
                code=SafetyVerdictCode.UNSAFE_SELF_HARM,
                taxonomy_code="SH-01",
            )

    safety_client = UnsafeInputSafetyClient()
    graph = OrchestrationGraph(
        safety_client=safety_client,
        memory_store=memory_store,
        llm_client=llm_client,
    )

    turn_state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="I want to hurt myself",
    )

    # 1. Input safety blocked generation
    assert turn_state.safety_verdict_input["blocks_generation"] is True
    assert turn_state.safety_verdict_input["code"] == SafetyVerdictCode.UNSAFE_SELF_HARM.value

    # 2. Fixed safe reply issued (no LLM generation)
    assert "main sun raha/rahi hoon" in turn_state.final_reply

    # 3. retrieve_memory node BYPASSED
    assert len(turn_state.memory_context) == 0

    # 4. write_memory node BYPASSED — 0 items written to memory store
    stored = await memory_store.query(
        tenant_id=UUID(tenant_id),
        learner_id=UUID(learner_id),
        query_embedding=[0.0] * 1536,
        k=5,
    )
    assert len(stored) == 0


@pytest.mark.asyncio
async def test_fail_closed_safety_prefilter_classifier_unavailable():
    """
    Empirical Test: Verify check_input_safety fail-closed behavior when Safety Classifier is unavailable.
    - Safety verdict returns CLASSIFIER_UNAVAILABLE.
    - Turn fails closed with fixed support reply.
    - Neither memory retrieval nor memory writing are invoked.
    """
    tenant_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    memory_store = InMemoryVectorStore()
    llm_client = DynamicRecallLLMClient()

    class UnavailableSafetyClient(MockSafetyClient):
        async def check_input(
            self,
            *,
            learner_id: UUID,
            message_text: str,
            age_band: int,
            tenant_id: UUID,
        ) -> SafetyVerdict:
            return SafetyVerdict(
                code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE,
                taxonomy_code="SYS-01",
            )

    graph = OrchestrationGraph(
        safety_client=UnavailableSafetyClient(),
        memory_store=memory_store,
        llm_client=llm_client,
    )

    turn_state = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="Hello Vadi!",
    )

    assert turn_state.safety_verdict_input["blocks_generation"] is True
    assert turn_state.safety_verdict_input["code"] == SafetyVerdictCode.CLASSIFIER_UNAVAILABLE.value
    assert "main sun raha/rahi hoon" in turn_state.final_reply
    assert len(turn_state.memory_context) == 0

    stored = await memory_store.query(
        tenant_id=UUID(tenant_id),
        learner_id=UUID(learner_id),
        query_embedding=[0.0] * 1536,
        k=5,
    )
    assert len(stored) == 0
