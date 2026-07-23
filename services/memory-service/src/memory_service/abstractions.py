"""
Abstract base classes and data models for Vadi-Pehn Multi-Hybrid RAG Pipeline.
Implements: AGENTS.md Part 3 (Abstract-first requirement),
PRD §4 (Memory & Context), SD §3.2 & §5.1 (Hybrid Retrieval, RRF, Reranking).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class ScoredMemoryItem:
    """Individual memory item with detailed dense, sparse, RRF, and rerank scores."""

    memory_id: UUID | str
    tenant_id: UUID
    learner_id: UUID
    content: str
    dense_score: float = 0.0
    sparse_score: float = 0.0
    dense_rank: int = 9999
    sparse_rank: int = 9999
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass
class HybridRetrievalQuery:
    """Configuration and query parameters for multi-hybrid RAG retrieval."""

    tenant_id: UUID
    learner_id: UUID
    query_text: str
    query_embedding: list[float]
    top_k: int = 5
    candidate_limit: int = 20
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    rrf_k: int = 60  # Standard constant k in Reciprocal Rank Fusion formula
    session_id: UUID | None = None


@dataclass
class ContextualTurnSummary:
    """Context window combining recent dialogue turns, retrieved memories, and rapport status."""

    session_history: list[dict[str, str]]
    retrieved_memories: list[ScoredMemoryItem]
    rapport_score: float
    matched_personas: list[dict[str, Any]] = field(default_factory=list)
    panel_introduced: bool = False


class EmbeddingClient(abc.ABC):
    """
    Abstract base class for text embedding generation.
    Stand-in implementations (MockEmbeddingClient) enable deterministic testing without external API calls.
    """

    @abc.abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate a normalized embedding vector for a single text string."""
        ...

    @abc.abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized embedding vectors for a batch of strings."""
        ...


class RerankerClient(abc.ABC):
    """
    Abstract base class for cross-encoder reranking over retrieved candidate items.
    """

    @abc.abstractmethod
    async def rerank(
        self, query: str, candidates: list[ScoredMemoryItem], top_k: int = 5
    ) -> list[ScoredMemoryItem]:
        """Score candidate items using cross-encoder relevance and return top_k sorted by `rerank_score`."""
        ...


class ConsentCheckerClient(abc.ABC):
    """
    Abstract interface for verifying active parental/learner consent before memory writing.
    Implements: PRD §3.2 (Consent Verification), Child Safety Non-Negotiable #1 & #6.
    """

    @abc.abstractmethod
    async def check_memory_write_consent(
        self, tenant_id: UUID, learner_id: UUID
    ) -> bool:
        """Return True if learner has active consent for memory_storage, False if revoked/absent."""
        ...


class QueryTransformer(abc.ABC):
    """
    Abstract base class for query rewriting and multi-query expansion.
    """

    @abc.abstractmethod
    async def transform(self, query: str) -> list[str]:
        """Rewrite and expand a query, returning a list of search queries."""
        ...

