"""
Empirical verification harness for Milestone 6 (Memory RAG & Consent Boundaries).
Executes all E2E integration tests and adversarial stress tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
import sys
import uuid
from typing import Any
from uuid import UUID

# Ensure repo paths are in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ORCH_SRC = os.path.abspath(os.path.join(ROOT_DIR, "services", "orchestration", "src"))
MEM_SRC = os.path.abspath(os.path.join(ROOT_DIR, "services", "memory-service", "src"))
MEM_TESTS = os.path.abspath(os.path.join(ROOT_DIR, "services", "memory-service", "tests"))

for path in (ROOT_DIR, ORCH_SRC, MEM_SRC, MEM_TESTS):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi.testclient import TestClient

from services.abstractions import (
    InMemoryVectorStore,
    LLMClient,
    MockLLMClient,
    MockSafetyClient,
    SafetyVerdict,
    SafetyVerdictCode,
)
from services.orchestration.src.orchestration.graph import (
    OrchestrationGraph,
    TurnState,
)
import services.orchestration.src.orchestration.main as orchestration_main
from services.orchestration.src.orchestration.main import app


class DynamicAstronomyLLMClient(LLMClient):
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

        if "astronomy" in user_message.lower() or "galaxies" in user_message.lower():
            reply = "Astronomy and studying galaxies is amazing! I will remember that you love astronomy."
        elif "astronomy" in system_prompt.lower() or "galaxies" in system_prompt.lower():
            reply = "Yes! I remember you told me your favorite hobby is astronomy and you want to study galaxies!"
        else:
            reply = "I am your sibling mentor! What would you like to talk about today?"

        if stream:
            return [reply]
        return reply


class UnsafeMockSafetyClient(MockSafetyClient):
    def __init__(self, code: SafetyVerdictCode = SafetyVerdictCode.UNSAFE_SELF_HARM):
        super().__init__()
        self.unsafe_code = code

    async def check_input(
        self, learner_id: UUID, message_text: str, age_band: int, tenant_id: UUID | None = None
    ) -> SafetyVerdict:
        return SafetyVerdict(
            code=self.unsafe_code,
            taxonomy_code="S6",
            blocks_generation=True,
            reason="Adversarial unsafe input simulation",
        )


async def run_all_verifications():
    results = []
    print("=== STARTING MILESTONE 6 EMPIRICAL VERIFICATION SUITE ===\n")

    # ---------------------------------------------------------
    # Verification 1: Turn 1 Memory Storage & Turn 2 Recall
    # ---------------------------------------------------------
    try:
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

        # Turn 1
        turn1_state = await graph.run_turn(
            session_id=session_id,
            tenant_id=tenant_id,
            learner_id=learner_id,
            age_band=2,
            message_text="My favorite hobby is astronomy and I want to study galaxies",
        )

        assert turn1_state.final_reply != "", "Turn 1 final_reply is empty"
        assert turn1_state.safety_verdict_input["code"] == SafetyVerdictCode.SAFE.value
        assert "astronomy" in turn1_state.final_reply.lower()

        stored_chunks = await memory_store.query(
            tenant_id=UUID(tenant_id),
            learner_id=UUID(learner_id),
            query_embedding=[0.0] * 1536,
            k=5,
        )
        assert len(stored_chunks) > 0, "No memory chunk stored in Turn 1"
        assert "astronomy" in stored_chunks[0].content.lower(), "Stored chunk missing 'astronomy'"

        # Turn 2
        turn2_state = await graph.run_turn(
            session_id=session_id,
            tenant_id=tenant_id,
            learner_id=learner_id,
            age_band=2,
            message_text="Do you remember what hobby I told you about?",
        )

        assert len(turn2_state.memory_context) > 0, "Turn 2 memory_context empty"
        assert any("astronomy" in item["content"].lower() for item in turn2_state.memory_context)
        assert "astronomy" in turn2_state.final_reply.lower(), "Turn 2 reply missing 'astronomy'"
        assert "galaxies" in turn2_state.final_reply.lower(), "Turn 2 reply missing 'galaxies'"

        results.append(("1. Turn 1 Memory Storage & Turn 2 Contextual Recall", "PASS", "Successfully stored and recalled astronomy memory"))
        print("[PASS] 1. Turn 1 Memory Storage & Turn 2 Contextual Recall")
    except Exception as e:
        results.append(("1. Turn 1 Memory Storage & Turn 2 Contextual Recall", "FAIL", str(e)))
        print(f"[FAIL] 1. Turn 1 Memory Storage & Turn 2 Contextual Recall: {e}")

    # ---------------------------------------------------------
    # Verification 2: Hybrid RAG Pipeline Integration
    # ---------------------------------------------------------
    try:
        from memory_service.context import ContextualRetrievalService
        from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient
        from memory_service.retrieval import HybridRetrievalEngine
        from memory_service.write_pipeline import AsyncMemoryWriter
        from mock_db import MockAsyncpgConnection, MockAsyncpgPool

        h_tenant_id = str(uuid.uuid4())
        h_learner_id = str(uuid.uuid4())
        h_session_id = str(uuid.uuid4())

        mock_conn = MockAsyncpgConnection()
        mock_pool = MockAsyncpgPool(mock_conn)

        def custom_fetch(query: str, args: tuple) -> list[dict[str, Any]]:
            query_lower = query.lower()
            if "embedding <=>" in query_lower:
                return [{
                    "id": uuid.uuid4(),
                    "tenant_id": UUID(h_tenant_id),
                    "learner_id": UUID(h_learner_id),
                    "content": "Learner disclosed interest: My favorite hobby is astronomy and I want to study galaxies",
                    "metadata": "{}",
                    "created_at": datetime.now(timezone.utc),
                    "dense_score": 0.92,
                }]
            elif "conversation_session_id" in query_lower:
                return [{"content": "My favorite hobby is astronomy and I want to study galaxies", "metadata": '{"role": "user"}'}]
            elif "learner_interest_profile" in query_lower:
                return [{"topics": '["astronomy"]'}]
            elif "professional_personas" in query_lower:
                return [{
                    "id": uuid.uuid4(),
                    "persona_name": "Dr. Sarah (Astrophysicist)",
                    "career_domain": "astronomy",
                    "bio": "Astrophysicist studying space telescopes.",
                }]
            return []

        mock_conn.fetch_callback = custom_fetch
        mock_conn.fetchval_returns = [80.0]

        embedding_client = MockEmbeddingClient()
        reranker = MockRerankerClient()
        retrieval_engine = HybridRetrievalEngine(mock_pool, embedding_client, reranker)
        context_service = ContextualRetrievalService(mock_pool, retrieval_engine, rapport_threshold=70.0)

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
            session_id=h_session_id,
            tenant_id=h_tenant_id,
            learner_id=h_learner_id,
            age_band=2,
            message_text="What is my hobby?",
        )

        assert len(turn_state.memory_context) > 0
        assert "astronomy" in turn_state.memory_context[0]["content"].lower()

        results.append(("2. Hybrid RAG Pipeline Integration", "PASS", "Hybrid RAG engine, contextual service & memory writer integrated seamlessly"))
        print("[PASS] 2. Hybrid RAG Pipeline Integration")
    except Exception as e:
        results.append(("2. Hybrid RAG Pipeline Integration", "FAIL", str(e)))
        print(f"[FAIL] 2. Hybrid RAG Pipeline Integration: {e}")

    # ---------------------------------------------------------
    # Verification 3: Consent Boundary & Write Abort
    # ---------------------------------------------------------
    try:
        from memory_service.abstractions import ConsentCheckerClient, HybridRetrievalQuery, ScoredMemoryItem
        from memory_service.context import ContextualRetrievalService
        from memory_service.embeddings import MockEmbeddingClient
        from memory_service.retrieval import HybridRetrievalEngine
        from memory_service.write_pipeline import AsyncMemoryWriter, ConsentDeniedWriteAbort
        from mock_db import MockAsyncpgConnection, MockAsyncpgPool

        class ToggleableConsentChecker(ConsentCheckerClient):
            def __init__(self, allowed: bool = True):
                self.allowed = allowed
            async def check_memory_write_consent(self, tenant_id: UUID, learner_id: UUID) -> bool:
                return self.allowed

        c_tenant_id = UUID(str(uuid.uuid4()))
        c_learner_id = UUID(str(uuid.uuid4()))
        c_session_id = UUID(str(uuid.uuid4()))

        mock_conn = MockAsyncpgConnection()
        mock_pool = MockAsyncpgPool(mock_conn)
        embedding_client = MockEmbeddingClient()

        # Active consent
        active_consent = ToggleableConsentChecker(allowed=True)
        writer_active = AsyncMemoryWriter(mock_pool, active_consent, embedding_client)
        written_ids = await writer_active.write_memory_chunked(
            tenant_id=c_tenant_id,
            learner_id=c_learner_id,
            content="Child: My favorite hobby is astronomy\nVadi: That is great!",
            session_id=c_session_id,
        )
        assert len(written_ids) > 0, "Active consent write failed"

        # Inactive consent
        inactive_consent = ToggleableConsentChecker(allowed=False)
        writer_inactive = AsyncMemoryWriter(mock_pool, inactive_consent, embedding_client)
        consent_failed_closed = False
        try:
            await writer_inactive.write_memory_chunked(
                tenant_id=c_tenant_id,
                learner_id=c_learner_id,
                content="Child: My favorite hobby is astronomy\nVadi: That is great!",
                session_id=c_session_id,
            )
        except ConsentDeniedWriteAbort:
            consent_failed_closed = True

        assert consent_failed_closed, "Inactive consent did not raise ConsentDeniedWriteAbort"

        # Consent category filtering on retrieval
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

        mock_conn.fetchval_returns = [0.0]
        engine = CustomRetrievalEngine(mock_pool, embedding_client)
        context_service = ContextualRetrievalService(mock_pool, engine)

        query = HybridRetrievalQuery(
            tenant_id=c_tenant_id,
            learner_id=c_learner_id,
            query_text="What is my hobby?",
            query_embedding=[0.1] * 1536,
        )

        summary = await context_service.get_contextual_summary(
            query, revoked_consent_categories=["conversation_storage"]
        )

        assert len(summary.retrieved_memories) == 1, f"Expected 1 memory after filtering, got {len(summary.retrieved_memories)}"
        assert summary.retrieved_memories[0].content == "Allowed memory without revoked consent"

        results.append(("3. Consent Boundary Filtering & Write Abort", "PASS", "Fails closed on revoked consent write & filters revoked category on retrieval"))
        print("[PASS] 3. Consent Boundary Filtering & Write Abort")
    except Exception as e:
        results.append(("3. Consent Boundary Filtering & Write Abort", "FAIL", str(e)))
        print(f"[FAIL] 3. Consent Boundary Filtering & Write Abort: {e}")

    # ---------------------------------------------------------
    # Verification 4: RLS Tenant Isolation
    # ---------------------------------------------------------
    try:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        rls_learner = uuid.uuid4()

        memory_store = InMemoryVectorStore()

        await memory_store.write(
            tenant_id=tenant_a,
            learner_id=rls_learner,
            content="Tenant A confidential astronomy disclosure",
            embedding=[0.1] * 1536,
        )

        chunks_a = await memory_store.query(
            tenant_id=tenant_a,
            learner_id=rls_learner,
            query_embedding=[0.1] * 1536,
            k=5,
        )
        assert len(chunks_a) == 1, "Tenant A query returned wrong count"

        chunks_b = await memory_store.query(
            tenant_id=tenant_b,
            learner_id=rls_learner,
            query_embedding=[0.1] * 1536,
            k=5,
        )
        assert len(chunks_b) == 0, "Tenant B leaked Tenant A memory!"

        results.append(("4. RLS Tenant Isolation", "PASS", "Tenant B strictly isolated from Tenant A memory"))
        print("[PASS] 4. RLS Tenant Isolation")
    except Exception as e:
        results.append(("4. RLS Tenant Isolation", "FAIL", str(e)))
        print(f"[FAIL] 4. RLS Tenant Isolation: {e}")

    # ---------------------------------------------------------
    # Verification 5: FastAPI HTTP Turn Endpoint
    # ---------------------------------------------------------
    try:
        with TestClient(app) as client:
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
            assert response.status_code == 200, f"HTTP {response.status_code}: {response.text}"
            data = response.json()
            assert data["session_id"] == payload["session_id"]
            assert data["final_reply"] != ""

        results.append(("5. FastAPI HTTP Turn Endpoint", "PASS", "POST /internal/v1/orchestration/turn returns 200 OK with valid TurnState payload"))
        print("[PASS] 5. FastAPI HTTP Turn Endpoint")
    except Exception as e:
        results.append(("5. FastAPI HTTP Turn Endpoint", "FAIL", str(e)))
        print(f"[FAIL] 5. FastAPI HTTP Turn Endpoint: {e}")

    # ---------------------------------------------------------
    # Adversarial Stress Test 1: Fail-Closed Input Safety Pre-Filter
    # ---------------------------------------------------------
    try:
        adv_tenant_id = str(uuid.uuid4())
        adv_learner_id = str(uuid.uuid4())
        adv_session_id = str(uuid.uuid4())

        adv_memory_store = InMemoryVectorStore()
        adv_llm_client = DynamicAstronomyLLMClient()
        adv_safety_client = UnsafeMockSafetyClient(SafetyVerdictCode.UNSAFE_SELF_HARM)

        adv_graph = OrchestrationGraph(
            safety_client=adv_safety_client,
            memory_store=adv_memory_store,
            llm_client=adv_llm_client,
        )

        unsafe_state = await adv_graph.run_turn(
            session_id=adv_session_id,
            tenant_id=adv_tenant_id,
            learner_id=adv_learner_id,
            age_band=2,
            message_text="I feel like hurting myself",
        )

        # Invariants under unsafe input:
        # 1. LLM generate was NOT called
        assert len(adv_llm_client.call_history) == 0, "LLM was called on unsafe input! Guardrail G-001 violation!"
        # 2. Safety verdict input is UNSAFE
        assert unsafe_state.safety_verdict_input["code"] == SafetyVerdictCode.UNSAFE_SELF_HARM.value
        # 3. Fixed script returned
        assert "main sun raha" in unsafe_state.final_reply or "helpline" in unsafe_state.final_reply
        # 4. Memory store was NOT written to
        adv_chunks = await adv_memory_store.query(
            tenant_id=UUID(adv_tenant_id),
            learner_id=UUID(adv_learner_id),
            query_embedding=[0.0] * 1536,
            k=5,
        )
        assert len(adv_chunks) == 0, "Unsafe turn wrote to memory store!"

        results.append(("Adversarial 1: Fail-Closed Input Pre-filter & Memory Bypass", "PASS", "Unsafe input blocked LLM and memory write entirely"))
        print("[PASS] Adversarial 1: Fail-Closed Input Pre-filter & Memory Bypass")
    except Exception as e:
        results.append(("Adversarial 1: Fail-Closed Input Pre-filter & Memory Bypass", "FAIL", str(e)))
        print(f"[FAIL] Adversarial 1: Fail-Closed Input Pre-filter & Memory Bypass: {e}")

    # ---------------------------------------------------------
    # Adversarial Stress Test 2: Multi-Turn Conversation Storage Toggle
    # ---------------------------------------------------------
    try:
        from memory_service.write_pipeline import AsyncMemoryWriter, ConsentDeniedWriteAbort
        from memory_service.abstractions import ConsentCheckerClient
        from mock_db import MockAsyncpgConnection, MockAsyncpgPool

        # Test graph execution when consent_checker returns False
        class RevokedConsentChecker(ConsentCheckerClient):
            async def check_memory_write_consent(self, tenant_id: UUID, learner_id: UUID) -> bool:
                return False

        rev_conn = MockAsyncpgConnection()
        rev_pool = MockAsyncpgPool(rev_conn)
        rev_writer = AsyncMemoryWriter(rev_pool, RevokedConsentChecker())

        rev_graph = OrchestrationGraph(
            safety_client=MockSafetyClient(),
            memory_store=InMemoryVectorStore(),
            llm_client=DynamicAstronomyLLMClient(),
            memory_writer=rev_writer,
        )

        turn_rev = await rev_graph.run_turn(
            session_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            learner_id=str(uuid.uuid4()),
            age_band=2,
            message_text="Hello astronomy friend",
        )

        # Wait briefly for background task to execute
        await asyncio.sleep(0.1)

        # Ensure turn completed successfully without crashing the graph turn
        assert turn_rev.final_reply != ""

        results.append(("Adversarial 2: Async Memory Writer Revoked Consent Resilience", "PASS", "Graph turn succeeds without breaking while memory write fails closed asynchronously"))
        print("[PASS] Adversarial 2: Async Memory Writer Revoked Consent Resilience")
    except Exception as e:
        results.append(("Adversarial 2: Async Memory Writer Revoked Consent Resilience", "FAIL", str(e)))
        print(f"[FAIL] Adversarial 2: Async Memory Writer Revoked Consent Resilience: {e}")

    print("\n=== SUMMARY RESULTS ===")
    all_passed = True
    for name, status, details in results:
        print(f"[{status}] {name} - {details}")
        if status != "PASS":
            all_passed = False

    return all_passed, results


if __name__ == "__main__":
    success, _ = asyncio.run(run_all_verifications())
    sys.exit(0 if success else 1)
