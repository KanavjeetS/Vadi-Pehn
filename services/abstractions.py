"""
Abstract base classes for all Vadi-Pehn services.
Implements: coding-standards §3 (abstract-first pattern).

Every module talking to an external system (LLM, DB, HTTP) exposes:
  1. An abstract base class (this file)
  2. A mock implementation (used in tests and dev)
  3. A production implementation (built per service build skill)

WHAT THIS IS: Shared interface definitions and safety type hierarchy.
WHAT THIS IS NOT: Production implementations (those live in each service).
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator
from uuid import UUID

# ─────────────────────────────────────────────────────────────────────────────
# Safety Types — used by every service that touches generation or safety checks
# PRD §8, SD §4.3
# ─────────────────────────────────────────────────────────────────────────────


class SafetyVerdictCode(str, Enum):
    """
    Verdict codes returned by the Safety Proxy.
    SAFE is the only code that allows generation to proceed.
    ALL other codes block generation — fail-closed invariant.
    Implements: GUARDRAILS G-001, PRD §8.1 (fail-closed behavior).
    """

    SAFE = "safe"
    UNSAFE_SELF_HARM = "unsafe_self_harm"  # Aegis S6 taxonomy
    UNSAFE_ABUSE_DISCLOSURE = "unsafe_abuse_disclosure"
    UNSAFE_GENERAL = "unsafe_general"
    CLASSIFIER_UNAVAILABLE = "classifier_unavailable"  # timeout / exception

    @property
    def blocks_generation(self) -> bool:
        """
        Returns True for every verdict that must block LLM generation.
        CRITICAL: Do NOT add SAFE to this list. Do NOT change this logic
        without @safety-engineer + @data-engineer dual review.
        """
        return self != SafetyVerdictCode.SAFE


@dataclass(frozen=True)
class SafetyVerdict:
    """Immutable verdict from the Safety Proxy."""

    code: SafetyVerdictCode
    taxonomy_code: str | None = None  # e.g. "S6" for self-harm
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float | None = None

    @property
    def blocks_generation(self) -> bool:
        return self.code.blocks_generation

    @classmethod
    def unavailable(cls) -> "SafetyVerdict":
        """Fail-closed factory: use when classifier times out or throws."""
        return cls(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE)


# ─────────────────────────────────────────────────────────────────────────────
# Memory Types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MemoryChunk:
    """A single retrieved memory chunk with its RLS-validated context."""

    chunk_id: str
    content: str
    embedding: list[float]
    tenant_id: UUID
    learner_id: UUID
    created_at: datetime
    similarity_score: float


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base: Safety Client
# PRD §8, SD §4.3
# ─────────────────────────────────────────────────────────────────────────────


class SafetyClient(ABC):
    """
    Abstract interface for the NeMo Guardrails Safety Proxy.
    Implements: coding-standards §3 (abstract-first pattern).
    PRD §8: input + output safety rails, fail-closed on timeout.
    """

    @abstractmethod
    async def check_input(
        self,
        *,
        learner_id: UUID,
        message_text: str,
        age_band: int,
        tenant_id: UUID,
    ) -> SafetyVerdict:
        """
        Check a child's input message before it reaches the LLM.
        MUST complete within 3 seconds — caller enforces timeout.
        On any exception: return SafetyVerdict.unavailable() (fail-closed).
        """
        ...

    @abstractmethod
    async def check_output(
        self,
        *,
        learner_id: UUID,
        draft_reply_text: str,
        tenant_id: UUID,
    ) -> SafetyVerdict:
        """
        Check a draft LLM reply before it is sent to the child or TTS.
        On voice path: called PER SENTENCE CHUNK (GUARDRAILS G-004).
        On any exception: return SafetyVerdict.unavailable() (fail-closed).
        """
        ...


class MockSafetyClient(SafetyClient):
    """
    Mock safety client for tests and local dev without vLLM.
    Returns SAFE for all inputs by default. Override blocked_patterns in tests
    to simulate unsafe verdicts.

    WHAT THIS IS: A test double. It does NOT implement any real safety logic.
    WHAT THIS IS NOT: A production safety implementation.
    """

    def __init__(
        self,
        default_verdict: SafetyVerdictCode = SafetyVerdictCode.SAFE,
        blocked_substrings: list[str] | None = None,
    ) -> None:
        self.default_verdict = default_verdict
        self.blocked_substrings = blocked_substrings or []
        self.input_calls: list[dict[str, Any]] = []
        self.output_calls: list[dict[str, Any]] = []

    async def check_input(
        self, *, learner_id: UUID, message_text: str, age_band: int, tenant_id: UUID
    ) -> SafetyVerdict:
        self.input_calls.append({"learner_id": learner_id, "text": message_text})
        for pattern in self.blocked_substrings:
            if pattern.lower() in message_text.lower():
                return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL)
        return SafetyVerdict(code=self.default_verdict)

    async def check_output(
        self, *, learner_id: UUID, draft_reply_text: str, tenant_id: UUID
    ) -> SafetyVerdict:
        self.output_calls.append({"learner_id": learner_id, "text": draft_reply_text})
        for pattern in self.blocked_substrings:
            if pattern.lower() in draft_reply_text.lower():
                return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL)
        return SafetyVerdict(code=self.default_verdict)


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base: Memory Store
# SD §3.2, §7.1
# ─────────────────────────────────────────────────────────────────────────────


class MemoryStore(ABC):
    """
    Abstract interface for the learner memory store (pgvector + RLS).
    SD §3.2: learner_memories table with HNSW index and per-transaction RLS.
    SD §7.1: every query must issue SET LOCAL app.current_tenant_id inside transaction.
    """

    @abstractmethod
    async def write(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Write a memory chunk. Returns chunk_id. RLS must be set in transaction."""
        ...

    @abstractmethod
    async def query(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[MemoryChunk]:
        """
        Retrieve top-k similar chunks for this learner.
        RLS transaction pattern (MUST be in implementation):
            SET LOCAL app.current_tenant_id = $tenant_id
            SET LOCAL hnsw.iterative_scan = relaxed_order
            SET LOCAL hnsw.max_scan_tuples = 20000
        """
        ...

    @abstractmethod
    async def delete_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> int:
        """
        Delete ALL memories for a learner (consent withdrawal trigger — PRD §3.4).
        Returns count of deleted rows.
        RLS must be set in transaction to prevent cross-tenant deletes.
        """
        ...

    @abstractmethod
    async def prune_expired(self, *, retention_months: int = 18) -> int:
        """
        Nightly pruning job — delete memories older than retention_months (PRD §3.4).
        Returns count of pruned rows.
        """
        ...


class InMemoryVectorStore(MemoryStore):
    """
    In-memory mock implementation for tests and local dev.
    Uses cosine similarity — does NOT implement RLS (test isolation is per-instance).

    WHAT THIS IS: The test backend. It stays even when PostgresMemoryStore is built.
    WHAT THIS IS NOT: A production implementation. No RLS, no persistence.
    Implements: coding-standards §3 (abstract-first, mock stays alongside real impl).
    """

    def __init__(self) -> None:
        # {tenant_id: {learner_id: [MemoryChunk]}}
        self._store: dict[str, dict[str, list[MemoryChunk]]] = {}

    async def write(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        chunk_id = hashlib.sha256(
            f"{tenant_id}{learner_id}{content}".encode()
        ).hexdigest()[:16]
        tenant_key = str(tenant_id)
        learner_key = str(learner_id)
        self._store.setdefault(tenant_key, {}).setdefault(learner_key, [])
        self._store[tenant_key][learner_key].append(
            MemoryChunk(
                chunk_id=chunk_id,
                content=content,
                embedding=embedding,
                tenant_id=tenant_id,
                learner_id=learner_id,
                created_at=datetime.now(timezone.utc),
                similarity_score=1.0,
            )
        )
        return chunk_id

    async def query(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[MemoryChunk]:
        chunks = self._store.get(str(tenant_id), {}).get(str(learner_id), [])
        return chunks[-k:] if chunks else []

    async def delete_for_learner(self, *, tenant_id: UUID, learner_id: UUID) -> int:
        tenant_store = self._store.get(str(tenant_id), {})
        chunks = tenant_store.pop(str(learner_id), [])
        return len(chunks)

    async def prune_expired(self, *, retention_months: int = 18) -> int:
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_months * 30)
        pruned = 0
        for tenant_store in self._store.values():
            for learner_id, chunks in tenant_store.items():
                before = len(chunks)
                tenant_store[learner_id] = [c for c in chunks if c.created_at > cutoff]
                pruned += before - len(tenant_store[learner_id])
        return pruned


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base: LLM Client
# SD §5.1, SD §10
# ─────────────────────────────────────────────────────────────────────────────


class LLMClient(ABC):
    """
    Abstract interface for the vLLM main model client.
    IMPORTANT: Orchestration NEVER calls this directly.
    It must go through the Safety Proxy — this client is owned by the safety proxy,
    not the orchestration service. (GUARDRAILS G-001)
    """

    @abstractmethod
    async def generate(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str | list[str]:
        """Generate a reply. Stream=True returns sentence chunks for voice path."""
        ...

    async def stream(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield provider chunks; production clients may override for token streaming."""
        result = await self.generate(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        if isinstance(result, str):
            yield result
            return
        for chunk in result:
            yield chunk


class MockLLMClient(LLMClient):
    """
    Mock LLM client for tests.
    Records all calls so tests can assert it was never called on unsafe input.

    WHAT THIS IS: Test double. Tracks call count + inputs.
    WHAT THIS IS NOT: A production LLM client.
    """

    def __init__(self, reply: str = "[MOCK REPLY]") -> None:
        self.reply = reply
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str | list[str]:
        self.call_count += 1
        self.calls.append({"messages": messages, "max_tokens": max_tokens})
        if stream:
            return [self.reply]
        return self.reply
