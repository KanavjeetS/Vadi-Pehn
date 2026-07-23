"""
Orchestration Service — LangGraph session graph for Vadi-Pehn.
Implements: SD §5.1 (text turn graph), §5.3 (escalation flow).
PRD §5 (agentic execution), §8 (safety rails).

Graph spine (DO NOT reorder or bypass):
  check_input_safety
    → [SAFE]    → retrieve_memory → detect_panel_trigger → generate_reply
                                                          → check_output_safety
                                                          → write_memory (async)
    → [UNSAFE]  → handle_unsafe_input → create_governance_incident

CRITICAL INVARIANTS (see GUARDRAILS.md):
  G-001: LLM is never called without passing through check_input_safety first.
  G-004: On voice path, check_output_safety is called PER CHUNK before TTS.
  No node producing user-facing text skips check_output_safety.
"""

from __future__ import annotations

import hashlib
import uuid
import os
import sys
from typing import Any, AsyncIterator, Literal
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
import jinja2
import httpx

# Import Langfuse observability decorators
from langfuse import observe, propagate_attributes

# Resolve internal/monorepo module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Add memory-service path dynamically
memory_service_src = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "memory-service", "src")
)
if memory_service_src not in sys.path:
    sys.path.insert(0, memory_service_src)

from services.abstractions import (  # noqa: E402
    LLMClient,
    MemoryChunk,
    MemoryStore,
    SafetyClient,
    SafetyVerdict,
    SafetyVerdictCode,
)
from services.config import settings  # noqa: E402

try:
    from orchestration.retrieval import OrchestrationRetrieval
except ImportError:
    from services.orchestration.src.orchestration.retrieval import (
        OrchestrationRetrieval,
    )



class GovernanceIncidentClient:
    """Abstract incident transport used by the orchestration safety path."""

    async def create_incident(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        category: str,
        transcript_excerpt: str,
    ) -> str:
        raise NotImplementedError


class HttpGovernanceIncidentClient(GovernanceIncidentClient):
    """Network client with direct paging fallback when Governance is unavailable."""

    async def create_incident(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        category: str,
        transcript_excerpt: str,
    ) -> str:
        payload = {
            "tenant_id": str(tenant_id),
            "learner_id": str(learner_id),
            "category": category,
            "transcript_excerpt": transcript_excerpt[:500],
        }
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    f"{settings.governance.url.rstrip('/')}/internal/v1/governance/incident",
                    json=payload,
                    headers=(
                        {"X-Internal-Service-Token": settings.internal_service_token}
                        if settings.internal_service_token
                        else {}
                    ),
                )
                response.raise_for_status()
                return str(response.json()["incident_id"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            await self._page_fallback(payload)
            return "pending_manual_review"

    async def _page_fallback(self, payload: dict[str, str]) -> None:
        if not settings.governance.sms_webhook_url:
            return
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    settings.governance.sms_webhook_url,
                    json=payload,
                    headers=(
                        {"X-Internal-Service-Token": settings.internal_service_token}
                        if settings.internal_service_token
                        else {}
                    ),
                )
        except httpx.HTTPError:
            return


try:
    from memory_service.abstractions import EmbeddingClient, HybridRetrievalQuery
    from memory_service.context import ContextualRetrievalService
    from memory_service.write_pipeline import AsyncMemoryWriter
except ImportError:
    # Fail-safe fallbacks for unit tests running in isolated environments
    EmbeddingClient = Any
    HybridRetrievalQuery = Any
    ContextualRetrievalService = Any
    AsyncMemoryWriter = Any


# ─────────────────────────────────────────────────────────────────────────────
# Session State (TurnState)
# Every field has a comment: what populates it, what consumes it.
# ─────────────────────────────────────────────────────────────────────────────


class TurnState(BaseModel):
    """
    Immutable-by-convention turn state threaded through the LangGraph graph.
    Populate fields only in the node that owns them.
    """

    # ── Identity (set by API layer before graph entry) ──
    session_id: str
    tenant_id: str  # UUID str — hashed for Langfuse traces
    learner_id: str  # UUID str — hashed for Langfuse traces
    age_band: int  # 8-10=1, 11-13=2, 14-17=3
    turn_id: str = ""  # set in check_input_safety
    turn_count: int = 1  # current session turn index (PRD §4.3)

    # ── Input (set by API layer) ──
    message_text: str
    language_detected: str = "en"

    # ── Safety (set by check_input_safety) ──
    safety_verdict_input: dict[str, Any] | None = None  # SafetyVerdict as dict

    # ── Memory (set by retrieve_memory) ──
    memory_context: list[dict[str, Any]] = []

    # ── Panel (set by detect_panel_trigger) ──
    panel_triggered: bool = False
    panel_id: str | None = None
    panel_result: dict[str, Any] | None = None
    unmatched_interest_queued: bool = False  # set if no taxonomy match found (PRD §5.2)

    # ── Generation (set by generate_reply) ──
    draft_reply: str = ""
    session_capped: bool = False  # True if daily session cap hit (PRD §4.3)
    ai_disclosure_added: bool = (
        False  # True if periodic AI identity disclosure added (PRD §4.1)
    )

    # ── Output Safety (set by check_output_safety) ──
    safety_verdict_output: dict[str, Any] | None = None

    # ── Final (set by check_output_safety or handle_unsafe_input) ──
    final_reply: str = ""

    # ── Incident (set by create_governance_incident) ──
    incident_id: str | None = None

    # ── Error tracking ──
    error: str | None = None


def _hash_id(id_str: str) -> str:
    """SHA-256 truncated hash — for Langfuse traces (never log raw learner/tenant IDs)."""
    return hashlib.sha256(id_str.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Node Implementations
# ─────────────────────────────────────────────────────────────────────────────


class OrchestrationGraph:
    """
    Builds and holds the compiled LangGraph graph for one-turn text conversations.
    Inject dependencies via __init__ to allow test doubles (coding-standards §3).
    """

    def __init__(
        self,
        safety_client: SafetyClient,
        memory_store: MemoryStore,
        llm_client: LLMClient,
        persona_template: str = "You are Vadi, a caring elder sibling AI. You are NOT a real person. {context}",
        embedding_client: EmbeddingClient | None = None,
        context_service: ContextualRetrievalService | None = None,
        memory_writer: AsyncMemoryWriter | None = None,
        governance_client: GovernanceIncidentClient | None = None,
    ) -> None:
        self.safety_client = safety_client
        self.memory_store = memory_store
        self.llm_client = llm_client
        self.persona_template = persona_template
        # Wire in Phase 4 Hybrid RAG components
        self.embedding_client = embedding_client
        self.context_service = context_service
        self.memory_writer = memory_writer
        self.governance_client = governance_client
        self._graph = self._build()

    def _load_jinja_persona(
        self, filename: str = "sibling.jinja2"
    ) -> jinja2.Template | None:
        """Loads the Sibling Mentor system template from a versioned JINJA2 file."""
        # Resolve the monorepo root (works for both desktop single-process and standalone service)
        _here = os.path.dirname(os.path.abspath(__file__))
        _svc_root = os.path.abspath(os.path.join(_here, "..", ".."))  # services/orchestration
        _mono_root = os.path.abspath(os.path.join(_here, "..", "..", "..", ".."))  # d:\Vadi Bhen
        base_paths = [
            os.path.join(_svc_root, "personas"),                          # services/orchestration/personas
            os.path.join(_mono_root, "services", "orchestration", "personas"),  # absolute monorepo path
            os.path.join(_here, "..", "personas"),                        # src/orchestration/../personas
            os.path.join(_here, "personas"),                              # src/orchestration/personas
        ]
        for path in base_paths:
            full = os.path.join(path, filename)
            if os.path.exists(full):
                try:
                    env = jinja2.Environment(
                        loader=jinja2.FileSystemLoader(os.path.abspath(path)),
                        autoescape=False,
                        keep_trailing_newline=True,
                    )
                    return env.get_template(filename)
                except Exception:
                    pass
        return None

    # ── Node: check_input_safety ──────────────────────────────────────────
    @observe(name="check_input_safety")
    async def check_input_safety(self, state: TurnState) -> TurnState:
        """
        MUST be the first node. Calls Safety Proxy check-input.
        On UNSAFE or UNAVAILABLE: blocks all downstream LLM nodes.
        GUARDRAILS G-001: LLM is never reached if this returns non-SAFE.
        """
        turn_id = str(uuid.uuid4())
        verdict: SafetyVerdict = await self.safety_client.check_input(
            learner_id=UUID(state.learner_id),
            message_text=state.message_text,
            age_band=state.age_band,
            tenant_id=UUID(state.tenant_id),
        )
        return state.model_copy(
            update={
                "turn_id": turn_id,
                "safety_verdict_input": {
                    "code": verdict.code.value,
                    "taxonomy_code": verdict.taxonomy_code,
                    "blocks_generation": verdict.blocks_generation,
                },
            }
        )

    # ── Routing: after check_input_safety ────────────────────────────────
    def _route_after_input_safety(
        self, state: TurnState
    ) -> Literal["retrieve_memory", "handle_unsafe_input"]:
        verdict = state.safety_verdict_input or {}
        if verdict.get("blocks_generation", True):
            return "handle_unsafe_input"
        return "retrieve_memory"

    def _route_after_output_safety(
        self, state: TurnState
    ) -> Literal["write_memory", "create_governance_incident"]:
        """Route incident turns to governance after their fixed reply is output-gated."""
        input_code = (state.safety_verdict_input or {}).get("code")
        if input_code != SafetyVerdictCode.SAFE.value:
            return "create_governance_incident"
        return "write_memory"

    # ── Node: retrieve_memory ─────────────────────────────────────────────
    @observe(name="retrieve_memory")
    async def retrieve_memory(self, state: TurnState) -> TurnState:
        """
        Retrieve relevant memory chunks for this learner+turn.
        Uses OrchestrationRetrieval with LIMIT 5 recency-based query fallback when vector embedding client is unavailable.
        """
        retriever = OrchestrationRetrieval(
            memory_store=self.memory_store,
            embedding_client=self.embedding_client,
            context_service=self.context_service,
        )
        memory_context, panel_intro, panel_res = await retriever.retrieve_context(
            tenant_id=UUID(state.tenant_id),
            learner_id=UUID(state.learner_id),
            query_text=state.message_text,
            session_id=UUID(state.session_id) if state.session_id else None,
            top_k=5,
        )
        update_dict: dict[str, Any] = {"memory_context": memory_context}
        if panel_intro:
            update_dict["panel_triggered"] = True
            update_dict["panel_result"] = panel_res
        return state.model_copy(update=update_dict)

    # ── Node: detect_panel_trigger ────────────────────────────────────────
    @observe(name="detect_panel_trigger")
    async def detect_panel_trigger(self, state: TurnState) -> TurnState:
        """
        Detect if the child's message triggers career-panel introductions.
        Uses explicit career-INTENT phrases only — avoids false positives from
        words like 'teacher' or 'future' used in non-career contexts.
        """
        if state.panel_triggered:
            return state

        # Require explicit career exploration intent, not any mention of these words.
        # Bad: "mere teacher strict hain" → should NOT trigger panel
        # Good: "doctor banna chahta hoon" → SHOULD trigger panel
        career_intent_phrases = [
            "banna chahta", "banna chahti", "ban-na chahta", "ban-na chahti",
            "kya banunga", "kya banugi", "kya banu",
            "career mein", "career banana", "career banani",
            "kaun sa career", "konsa career",
            "future career", "mera career",
            "job kaise milti", "job kaise milega", "job chahiye",
            "profession choose", "kya profession",
            "engineer banna", "doctor banna", "farmer banna",
            "nurse banna", "pilot banna", "scientist banna",
            "business karna", "startup karna",
            "what career", "which career", "career advice",
            "i want to become", "i want to be a",
        ]
        text_lower = state.message_text.lower()
        triggered = any(phrase in text_lower for phrase in career_intent_phrases)
        return state.model_copy(update={"panel_triggered": triggered})

    def _resolve_career_persona_template(self, state: TurnState) -> str:
        """Look up matching career persona template file for triggered career exploration."""
        if state.panel_result and isinstance(state.panel_result, dict):
            personas = state.panel_result.get("personas", [])
            if personas and isinstance(personas, list) and len(personas) > 0:
                p_code = str(personas[0]).lower()
                candidate_name = f"{p_code}.jinja2"
                if self._load_jinja_persona(candidate_name):
                    return candidate_name

        text_lower = state.message_text.lower()
        if any(kw in text_lower for kw in ["doctor", "health", "nurse", "medical", "hospital", "medicine"]):
            return "doctor.jinja2"
        if any(kw in text_lower for kw in ["engineer", "robotics", "coder", "software", "tech", "programmer"]):
            return "engineer.jinja2"
        if any(kw in text_lower for kw in ["artist", "art", "design", "draw", "paint", "animation"]):
            return "artist.jinja2"
        if any(kw in text_lower for kw in ["scientist", "data", "research"]):
            return "data_scientist.jinja2"
        if any(kw in text_lower for kw in ["teacher", "education", "school"]):
            return "edu_teach.jinja2"

        return "engineer.jinja2"

    # ── Node: generate_reply ──────────────────────────────────────────────
    @observe(name="generate_reply")
    async def generate_reply(self, state: TurnState) -> TurnState:
        """
        Call LLM via Safety Proxy and generate a reply.
        Renders sibling.jinja2 prompt template to supply context and age-band variables.
        Enforces PRD §4.1 (AI Disclosure), PRD §4.3 (Session Wind-down Cap), and PRD §5.2 (Unmatched Interest Fallback).
        """
        # PRD §4.3: Session-duration / turn-count wind-down cap
        MAX_DAILY_TURNS = 20
        if state.turn_count >= MAX_DAILY_TURNS:
            wind_down = "Aaj ke liye humne kafi baatein kar li hain! Chalo abhi rest karte hain aur baki baatein kal karenge."
            return state.model_copy(
                update={
                    "draft_reply": wind_down,
                    "session_capped": True,
                }
            )

        # Load and render system prompt template from Jinja2
        context_text = "\n".join(c["content"] for c in state.memory_context)
        jinja_template = self._load_jinja_persona("sibling.jinja2")

        if jinja_template:
            system_prompt = jinja_template.render(
                context=context_text,
                age_band=state.age_band,
                language=state.language_detected,
            )
        else:
            # Fallback to init string if jinja2 template not found
            system_prompt = self.persona_template.format(context=context_text)

        # PRD §5.2: Unmatched interest fallback
        is_no_match = False
        if state.panel_result and isinstance(state.panel_result, dict):
            is_no_match = state.panel_result.get("panel_status") == "no_match_fallback"

        if is_no_match:
            draft = "yeh ek bohot unique aur naya interest hai! Main is par research karke tumhe kal detailed info bataunga."
            return state.model_copy(
                update={
                    "draft_reply": draft,
                    "unmatched_interest_queued": True,
                }
            )

        if state.panel_triggered and not state.final_reply:
            # Panel triggered — look up matching career persona template and render into system prompt
            career_template_name = self._resolve_career_persona_template(state)
            career_template = self._load_jinja_persona(career_template_name)
            career_context_str = ""
            if career_template:
                career_context_str = career_template.render(
                    age_band=state.age_band,
                    language=state.language_detected,
                    context=context_text,
                )

            panel_system = system_prompt
            if career_context_str:
                panel_system += f"\n\n[CAREER PERSONA CONTEXT ({career_template_name})]\n{career_context_str}"
            panel_system += (
                "\n\n[CAREER PANEL NOTE] Bacche ne career/future ke baare mein poochha hai. "
                "Apne mentor network ke baare mein naturally baat karo jaise ek bada bhai/behen karta hai. "
                "Enthusiastic raho, specific career ke baare mein curious sawal puchho. "
                "Koi fixed script mat use karo — bilkul original aur warm response do."
            )
            messages = [
                {"role": "system", "content": panel_system},
                {"role": "user", "content": state.message_text},
            ]
            draft = await self.llm_client.generate(messages=messages, temperature=0.8)
            if isinstance(draft, list):
                draft = " ".join(draft)
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state.message_text},
            ]
            draft = await self.llm_client.generate(messages=messages, temperature=0.7)
            if isinstance(draft, list):
                draft = " ".join(draft)

        # PRD §4.1: Persistent AI identity disclosure (every 5 turns or when attachment triggered)
        disclosure_added = False
        attachment_terms = ["best friend", "asli bhai", "real brother", "only friend"]
        is_attachment_expressed = any(
            term in state.message_text.lower() for term in attachment_terms
        )
        if state.turn_count % 5 == 0 or is_attachment_expressed:
            ai_note = " (jaise maine bataya, main ek AI mentor hoon, asli brother nahi, par tumhari madad karke mujhe bahut khushi hoti hai)"
            draft += ai_note
            disclosure_added = True

        return state.model_copy(
            update={
                "draft_reply": draft,
                "ai_disclosure_added": disclosure_added,
            }
        )

    async def stream_reply(self, state: TurnState) -> AsyncIterator[str]:
        """Stream a safety-prechecked draft for the voice gateway.

        The voice pipeline owns the input safety check before calling this
        method and output safety for every sentence before TTS.
        """
        verdict = state.safety_verdict_input or {}
        if verdict.get("blocks_generation", True):
            raise RuntimeError("Cannot stream an unverified or unsafe turn")

        memory_state = await self.retrieve_memory(state)
        panel_state = await self.detect_panel_trigger(memory_state)
        if panel_state.panel_triggered:
            yield "yeh ek bahut acha sawal hai — mujhe apne doston se puchne do, ek second!"
            return

        context_text = "\n".join(c["content"] for c in panel_state.memory_context)
        jinja_template = self._load_jinja_persona("sibling.jinja2")
        if jinja_template:
            system_prompt = jinja_template.render(
                context=context_text,
                age_band=state.age_band,
                language=state.language_detected,
            )
        else:
            system_prompt = self.persona_template.format(context=context_text)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state.message_text},
        ]
        async for chunk in self.llm_client.stream(messages=messages, temperature=0.7):
            if chunk:
                yield chunk

    # ── Node: check_output_safety ─────────────────────────────────────────
    @observe(name="check_output_safety")
    async def check_output_safety(self, state: TurnState) -> TurnState:
        """
        Check draft reply before it reaches the child.
        GUARDRAILS G-004: never skip this step on any path.
        """
        verdict: SafetyVerdict = await self.safety_client.check_output(
            learner_id=UUID(state.learner_id),
            draft_reply_text=state.draft_reply,
            tenant_id=UUID(state.tenant_id),
        )
        verdict_dict = {
            "code": verdict.code.value,
            "blocks_generation": verdict.blocks_generation,
        }
        # If output unsafe: replace with a safe fallback — do not surface raw error
        if verdict.blocks_generation:
            fallback = "I'm sorry, let me think of a better way to say that."
            fallback_verdict: SafetyVerdict = await self.safety_client.check_output(
                learner_id=UUID(state.learner_id),
                draft_reply_text=fallback,
                tenant_id=UUID(state.tenant_id),
            )
            final = "" if fallback_verdict.blocks_generation else fallback
            verdict_dict["fallback_code"] = fallback_verdict.code.value
        else:
            final = state.draft_reply

        return state.model_copy(
            update={
                "safety_verdict_output": verdict_dict,
                "final_reply": final,
            }
        )

    # ── Node: write_memory ────────────────────────────────────────────────
    @observe(name="write_memory")
    async def write_memory(self, state: TurnState) -> TurnState:
        """
        Write this turn's text to memory AFTER reply is delivered (async).
        Wired with AsyncMemoryWriter to check consent and write asynchronously.
        """
        input_code = (state.safety_verdict_input or {}).get("code")
        if not state.final_reply or input_code != SafetyVerdictCode.SAFE.value:
            return state

        if self.memory_writer:
            self.memory_writer.write_memory_async(
                tenant_id=UUID(state.tenant_id),
                learner_id=UUID(state.learner_id),
                content=f"Child: {state.message_text}\nVadi: {state.final_reply}",
                session_id=UUID(state.session_id) if state.session_id else None,
                metadata={
                    "role": "assistant",
                    "turn_id": state.turn_id,
                },
            )
        else:
            # Fallback legacy memory store query
            stub_embedding = [0.0] * 1536
            await self.memory_store.write(
                tenant_id=UUID(state.tenant_id),
                learner_id=UUID(state.learner_id),
                content=f"Child: {state.message_text}\nVadi: {state.final_reply}",
                embedding=stub_embedding,
            )
        return state

    # ── Node: handle_unsafe_input ─────────────────────────────────────────
    @observe(name="handle_unsafe_input")
    async def handle_unsafe_input(self, state: TurnState) -> TurnState:
        """
        Handle unsafe input without involving the LLM.
        Fixed script — never generated (PRD §3.3, §8.1).
        """
        verdict_code = (state.safety_verdict_input or {}).get("code", "unsafe_general")

        if verdict_code in (
            "unsafe_self_harm",
            "unsafe_abuse_disclosure",
            "classifier_unavailable",
        ):
            fixed_reply = (
                "main sun raha/rahi hoon. jo tum share kar rahe ho woh bahut bhari baat hai. "
                "please kisi bade pe bharosa karo — teacher, ghar mein koi, ya helpline. "
                "tum akele nahi ho."
            )
        else:
            fixed_reply = "main is vishay par baat nahi kar sakta, lekin doosre kisi cheez mein madad kar sakta hoon?"

        return state.model_copy(
            update={
                "final_reply": fixed_reply,
                "draft_reply": fixed_reply,
            }
        )

    # ── Node: create_governance_incident ──────────────────────────────────
    @observe(name="create_governance_incident")
    async def create_governance_incident(self, state: TurnState) -> TurnState:
        """
        Write safety incident to Governance DB via Governance Service.
        """
        verdict_code = (state.safety_verdict_input or {}).get("code", "")
        if verdict_code in (
            "unsafe_self_harm",
            "unsafe_abuse_disclosure",
            "classifier_unavailable",
        ):
            incident_id = str(uuid.uuid4())
            if self.governance_client:
                incident_id = await self.governance_client.create_incident(
                    tenant_id=UUID(state.tenant_id),
                    learner_id=UUID(state.learner_id),
                    category=verdict_code,
                    transcript_excerpt=state.message_text,
                )
            print(
                f"[INCIDENT] {incident_id} | severity={verdict_code} | learner={_hash_id(state.learner_id)}"
            )
            return state.model_copy(update={"incident_id": incident_id})
        return state

    # ── Graph Builder ─────────────────────────────────────────────────────
    def _build(self) -> Any:
        """
        Compile the LangGraph graph. Node order is load-bearing — do not reorder.
        """
        g = StateGraph(TurnState)

        # Add nodes
        g.add_node("check_input_safety", self.check_input_safety)
        g.add_node("retrieve_memory", self.retrieve_memory)
        g.add_node("detect_panel_trigger", self.detect_panel_trigger)
        g.add_node("generate_reply", self.generate_reply)
        g.add_node("check_output_safety", self.check_output_safety)
        g.add_node("write_memory", self.write_memory)
        g.add_node("handle_unsafe_input", self.handle_unsafe_input)
        g.add_node("create_governance_incident", self.create_governance_incident)

        # Entry point
        g.add_edge(START, "check_input_safety")

        # Conditional routing after input safety
        g.add_conditional_edges(
            "check_input_safety",
            self._route_after_input_safety,
            {
                "retrieve_memory": "retrieve_memory",
                "handle_unsafe_input": "handle_unsafe_input",
            },
        )

        # Safe path
        g.add_edge("retrieve_memory", "detect_panel_trigger")
        g.add_edge("detect_panel_trigger", "generate_reply")
        g.add_edge("generate_reply", "check_output_safety")
        g.add_conditional_edges(
            "check_output_safety",
            self._route_after_output_safety,
            {
                "write_memory": "write_memory",
                "create_governance_incident": "create_governance_incident",
            },
        )
        g.add_edge("write_memory", END)

        # Unsafe path
        g.add_edge("handle_unsafe_input", "check_output_safety")
        g.add_edge("create_governance_incident", END)

        return g.compile()

    @observe(name="vadi_pehn_turn")
    async def run_turn(
        self,
        *,
        session_id: str,
        tenant_id: str,
        learner_id: str,
        age_band: int,
        message_text: str,
        language: str = "hi",
    ) -> TurnState:
        """Run one conversation turn through the full graph."""
        initial_state = TurnState(
            session_id=session_id,
            tenant_id=tenant_id,
            learner_id=learner_id,
            age_band=age_band,
            message_text=message_text,
            language_detected=language,
        )
        # Update Langfuse trace metadata via propagate_attributes if library is active
        try:
            with propagate_attributes(
                user_id=_hash_id(learner_id),
                session_id=session_id,
                tags=["age_band_" + str(age_band)],
                metadata={
                    "tenant_id": _hash_id(tenant_id),
                    "language": language,
                },
            ):
                result = await self._graph.ainvoke(initial_state)
        except Exception:
            result = await self._graph.ainvoke(initial_state)

        return TurnState(**result)
