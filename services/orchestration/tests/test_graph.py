"""
Orchestration graph tests — proves all critical invariants.
Implements: PRD §14 (testing strategy), GUARDRAILS invariant verification.

Critical assertions:
  1. Unsafe input NEVER reaches LLM (llm_client.call_count == 0 after unsafe input)
  2. Output safety IS called on every safe turn
  3. Governance incident IS created on self-harm input
  4. Final reply is NEVER the raw draft if output safety blocks it
"""

from __future__ import annotations

import uuid

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from services.abstractions import (
    InMemoryVectorStore,
    MockLLMClient,
    MockSafetyClient,
    SafetyVerdictCode,
)
from services.orchestration.src.orchestration.graph import (
    GovernanceIncidentClient,
    OrchestrationGraph,
    TurnState,
)


def _make_ids() -> dict[str, str]:
    return {
        "session_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "learner_id": str(uuid.uuid4()),
    }


@pytest.fixture
def safe_graph() -> OrchestrationGraph:
    """Graph with MockSafetyClient (always SAFE) and MockLLMClient."""
    return OrchestrationGraph(
        safety_client=MockSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="Yeh bahut acha sawal hai!"),
    )


@pytest.fixture
def self_harm_graph() -> OrchestrationGraph:
    """Graph with unsafe input and a safe output rail for the fixed script."""

    class SelfHarmSafetyClient(MockSafetyClient):
        async def check_input(self, *, learner_id, message_text, age_band, tenant_id):
            from services.abstractions import SafetyVerdict

            return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_SELF_HARM)

        async def check_output(self, *, learner_id, draft_reply_text, tenant_id):
            from services.abstractions import SafetyVerdict

            return SafetyVerdict(code=SafetyVerdictCode.SAFE)

    return OrchestrationGraph(
        safety_client=SelfHarmSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="should never be seen"),
    )


@pytest.fixture
def unsafe_output_graph() -> OrchestrationGraph:
    """Graph where input is SAFE but output check returns UNSAFE_GENERAL."""

    class MixedSafetyClient(MockSafetyClient):
        async def check_output(self, *, learner_id, draft_reply_text, tenant_id):
            from services.abstractions import SafetyVerdict

            return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL)

    return OrchestrationGraph(
        safety_client=MixedSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="[MOCK REPLY]"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 1: Unsafe input never reaches LLM (GUARDRAILS G-001)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsafe_input_never_calls_llm(
    self_harm_graph: OrchestrationGraph,
) -> None:
    """
    CRITICAL: LLM must NOT be called when input safety verdict is non-SAFE.
    If this test fails, GUARDRAILS G-001 is violated.
    """
    ids = _make_ids()
    result = await self_harm_graph.run_turn(
        **ids, age_band=2, message_text="mujhe bahut bura lag raha hai"
    )
    # LLM must have zero calls
    assert self_harm_graph.llm_client.call_count == 0, (  # type: ignore[attr-defined]
        "GUARDRAILS G-001 VIOLATION: LLM was called despite unsafe input verdict"
    )
    # Must have a final reply (the fixed script)
    assert result.final_reply != ""
    assert result.incident_id is not None


@pytest.mark.asyncio
async def test_stream_reply_rejects_unchecked_turn(
    safe_graph: OrchestrationGraph,
) -> None:
    """Streaming cannot bypass the mandatory input safety node."""
    state = TurnState(
        **_make_ids(), age_band=2, message_text="[SYNTHETIC_TEST_CASE] hello"
    )

    with pytest.raises(RuntimeError, match="unverified or unsafe"):
        _ = [chunk async for chunk in safe_graph.stream_reply(state)]


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 2: Output safety IS called on every safe turn
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_output_safety_called_on_safe_turn(
    safe_graph: OrchestrationGraph,
) -> None:
    """Output safety client must be called even on fully safe turns (GUARDRAILS G-004)."""
    ids = _make_ids()
    await safe_graph.run_turn(
        **ids, age_band=1, message_text="aaj school mein kya hua?"
    )
    assert len(safe_graph.safety_client.output_calls) == 1  # type: ignore[attr-defined]
    assert len(safe_graph.safety_client.input_calls) == 1  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 3: Unsafe output never reaches child
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsafe_output_replaced_with_fallback(
    unsafe_output_graph: OrchestrationGraph,
) -> None:
    """
    If output safety blocks the draft reply, final_reply must NOT be the draft.
    Child must receive a safe fallback, not an unsafe LLM output.
    """
    ids = _make_ids()
    result = await unsafe_output_graph.run_turn(
        **ids, age_band=1, message_text="hello!"
    )
    assert result.draft_reply == "[MOCK REPLY]"
    assert (
        result.final_reply != "[MOCK REPLY]"
    ), "Unsafe output leaked to final_reply — output safety gate bypassed"
    assert result.safety_verdict_output is not None
    assert result.safety_verdict_output["blocks_generation"] is True


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 4: Governance incident created on self-harm
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_incident_created_on_self_harm(
    self_harm_graph: OrchestrationGraph,
) -> None:
    """Safety incident must be created when self-harm classifier fires (PRD §3.3)."""
    ids = _make_ids()
    result = await self_harm_graph.run_turn(**ids, age_band=2, message_text="trigger")
    assert result.incident_id is not None
    assert len(result.incident_id) > 0


@pytest.mark.asyncio
async def test_incident_is_sent_to_governance_client() -> None:
    class FakeGovernanceClient(GovernanceIncidentClient):
        def __init__(self) -> None:
            self.calls = []

        async def create_incident(self, **kwargs):
            self.calls.append(kwargs)
            return "inc_governance_test"

    governance = FakeGovernanceClient()
    graph = OrchestrationGraph(
        safety_client=MockSafetyClient(
            default_verdict=SafetyVerdictCode.UNSAFE_SELF_HARM
        ),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(),
        governance_client=governance,
    )
    ids = _make_ids()

    result = await graph.run_turn(
        **ids, age_band=2, message_text="synthetic safety case"
    )

    assert result.incident_id == "inc_governance_test"
    assert governance.calls[0]["category"] == "unsafe_self_harm"


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 5: Classifier unavailable → blocks generation (fail-closed)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classifier_unavailable_blocks_generation() -> None:
    """
    When classifier returns UNAVAILABLE (timeout/exception), generation must be blocked.
    GUARDRAILS G-001: fail-closed — UNAVAILABLE never means 'proceed'.
    """
    unavailable_graph = OrchestrationGraph(
        safety_client=MockSafetyClient(
            default_verdict=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE
        ),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="should not be seen"),
    )
    ids = _make_ids()
    await unavailable_graph.run_turn(**ids, age_band=1, message_text="hello")
    assert unavailable_graph.llm_client.call_count == 0, (  # type: ignore[attr-defined]
        "GUARDRAILS G-001 VIOLATION: classifier_unavailable must block generation"
    )


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 6: Happy path produces final reply
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_produces_reply(safe_graph: OrchestrationGraph) -> None:
    """Basic smoke test: safe input → safe output → non-empty final_reply."""
    ids = _make_ids()
    result = await safe_graph.run_turn(
        **ids, age_band=2, message_text="mera favorite subject math hai"
    )
    assert result.final_reply != ""
    assert result.error is None
    assert result.safety_verdict_input is not None
    assert result.safety_verdict_output is not None


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 7: Memory write after turn (not blocking)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_written_after_safe_turn(safe_graph: OrchestrationGraph) -> None:
    """After a safe turn, memory should contain the conversation exchange."""
    ids = _make_ids()
    await safe_graph.run_turn(
        **ids, age_band=1, message_text="mujhe cricket pasand hai"
    )
    chunks = await safe_graph.memory_store.query(
        tenant_id=__import__("uuid").UUID(ids["tenant_id"]),
        learner_id=__import__("uuid").UUID(ids["learner_id"]),
        query_embedding=[0.0] * 1536,
        k=5,
    )
    assert len(chunks) > 0
    assert "cricket" in chunks[0].content.lower()


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 8: Emotional Safety, AI Disclosure & Session Cap (PRD §4)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_cap_wind_down(safe_graph: OrchestrationGraph) -> None:
    """PRD §4.3: Turn count >= 20 triggers gentle wind-down message."""
    ids = _make_ids()
    state = TurnState(
        **ids,
        age_band=2,
        message_text="kya hum aur baat kar sakte hain?",
        turn_count=20,
    )
    result = await safe_graph._graph.ainvoke(state)
    res_state = TurnState(**result)
    assert res_state.session_capped is True
    assert "aaj ke liye humne kafi baatein" in res_state.draft_reply.lower()


@pytest.mark.asyncio
async def test_ai_identity_disclosure(safe_graph: OrchestrationGraph) -> None:
    """PRD §4.1: Expressing strong attachment appends AI identity disclosure."""
    ids = _make_ids()
    state = TurnState(
        **ids,
        age_band=2,
        message_text="you are my best friend and real brother",
        turn_count=1,
    )
    result = await safe_graph._graph.ainvoke(state)
    res_state = TurnState(**result)
    assert res_state.ai_disclosure_added is True
    assert "main ek ai mentor hoon" in res_state.draft_reply.lower()


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 9: Memory Reads & Recency Fallback (LIMIT 5)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recency_memory_retrieval_fallback() -> None:
    """Verify LIMIT 5 recency-based query fallback populates memory_context when embedding client is unavailable."""
    store = InMemoryVectorStore()
    tenant_id = uuid.uuid4()
    learner_id = uuid.uuid4()

    # Pre-populate 6 memory chunks
    for i in range(6):
        await store.write(
            tenant_id=tenant_id,
            learner_id=learner_id,
            content=f"Child: Memory turn {i}\nVadi: Reply {i}",
            embedding=[0.0] * 1536,
        )

    graph = OrchestrationGraph(
        safety_client=MockSafetyClient(),
        memory_store=store,
        llm_client=MockLLMClient(reply="Test response"),
        embedding_client=None,  # Unavailable embedding client
        context_service=None,
    )

    result = await graph.run_turn(
        session_id=str(uuid.uuid4()),
        tenant_id=str(tenant_id),
        learner_id=str(learner_id),
        age_band=2,
        message_text="Hello, do you remember me?",
    )

    # Should have fallback memory context populated with LIMIT 5 chunks
    assert len(result.memory_context) == 5
    assert "Memory turn 5" in result.memory_context[-1]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 10: Career Panel Template Rendering
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_career_panel_jinja_persona_rendering() -> None:
    """When panel_triggered=True, graph renders matching career persona template into prompt context."""
    for career_topic, expected_keyword in [
        ("I want to become a doctor", "Dr. Ananya"),
        ("engineer banna chahta hoon", "Rahul Bhaiya"),
        ("I want to be an artist and painter", "Maya Didi"),
    ]:
        graph = OrchestrationGraph(
            safety_client=MockSafetyClient(),
            memory_store=InMemoryVectorStore(),
            llm_client=MockLLMClient(reply="Career guidance response"),
        )
        ids = _make_ids()
        result = await graph.run_turn(
            **ids, age_band=2, message_text=f"Mujhe {career_topic}"
        )
        assert result.panel_triggered is True
        # Verify LLM system prompt received rendered career persona template
        last_messages = graph.llm_client.calls[-1]["messages"]  # type: ignore[attr-defined]
        system_msg = last_messages[0]["content"]
        assert expected_keyword in system_msg or "CAREER PERSONA CONTEXT" in system_msg


# ─────────────────────────────────────────────────────────────────────────────
# INVARIANT 11: Memory Write Format Verification
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_write_format(safe_graph: OrchestrationGraph) -> None:
    """Verify AsyncMemoryWriter / memory_store saves 'Child: {message}\nVadi: {reply}'."""
    ids = _make_ids()
    msg = "I love learning about astronomy!"
    res = await safe_graph.run_turn(**ids, age_band=2, message_text=msg)

    chunks = await safe_graph.memory_store.query(
        tenant_id=uuid.UUID(ids["tenant_id"]),
        learner_id=uuid.UUID(ids["learner_id"]),
        query_embedding=[0.0] * 1536,
        k=5,
    )
    assert len(chunks) > 0
    saved_content = chunks[0].content
    assert saved_content.startswith(f"Child: {msg}")
    assert f"Vadi: {res.final_reply}" in saved_content

