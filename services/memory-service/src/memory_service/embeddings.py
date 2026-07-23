"""
Embedding and Reranking client implementations (`services/memory-service/embeddings.py`).
Implements: PRD §4, SD §3.2, implementation_plan.md §4A & §4B.
Provides production `NomicEmbeddingClient` / `OpenAIEmbeddingClient` and deterministic `MockEmbeddingClient` / `MockRerankerClient`.
"""

from __future__ import annotations

import hashlib
import math

import httpx

from memory_service.abstractions import (
    EmbeddingClient,
    RerankerClient,
    ScoredMemoryItem,
)


class NomicEmbeddingClient(EmbeddingClient):
    """
    Production embedding client targeting local Ollama / nomic-embed-text or compatible API endpoint.
    Produces unit-normalized L2 vectors suitable for pgvector `vector_cosine_ops` HNSW indexing.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        dimensions: int = 1536,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self._http_client = http_client

    def _normalize_vector(self, vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vec))
        if norm <= 1e-9:
            return [0.0] * len(vec)
        return [v / norm for v in vec]

    async def embed_text(self, text: str) -> list[float]:
        client = self._http_client or httpx.AsyncClient()
        close_client = self._http_client is None
        try:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            raw_vec = data.get("embedding", [])
            if not raw_vec:
                raise ValueError("Received empty vector from embedding service")
            # If raw dimensions differ, truncate or zero-pad to match required schema
            if len(raw_vec) > self.dimensions:
                raw_vec = raw_vec[: self.dimensions]
            elif len(raw_vec) < self.dimensions:
                raw_vec.extend([0.0] * (self.dimensions - len(raw_vec)))
            return self._normalize_vector(raw_vec)
        finally:
            if close_client:
                await client.aclose()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # For endpoints without native multi-prompt batching, process sequentially or via asyncio.gather
        results = []
        for t in texts:
            vec = await self.embed_text(t)
            results.append(vec)
        return results


class MockEmbeddingClient(EmbeddingClient):
    """
    Deterministic mock embedding client generating reproducible 1536-dim unit vectors.
    Implements: AGENTS.md Part 3 (Abstract-first stand-in requirement).
    """

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def _generate_deterministic_vec(self, text: str) -> list[float]:
        # Hash text string into pseudo-random deterministic floats
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(self.dimensions):
            byte_val = h[i % len(h)]
            # Map byte [0, 255] to float in [-1.0, 1.0] with varying phase
            val = math.sin((byte_val + i) * 0.1)
            vec.append(val)
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec]

    async def embed_text(self, text: str) -> list[float]:
        return self._generate_deterministic_vec(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_deterministic_vec(t) for t in texts]


class MockRerankerClient(RerankerClient):
    """
    Cross-encoder reranking stand-in combining RRF base scores with token and exact phrase overlap.
    Boosts items containing exact query terms or specific named entities.
    """

    async def rerank(
        self, query: str, candidates: list[ScoredMemoryItem], top_k: int = 5
    ) -> list[ScoredMemoryItem]:
        if not candidates:
            return []

        query_lower = query.lower().strip()
        query_words = set(query_lower.split())

        scored_candidates = []
        for item in candidates:
            content_lower = item.content.lower()
            # Base rerank starts from normalized RRF
            score = item.rrf_score * 10.0

            # Boost if exact query phrase appears in candidate content
            if query_lower and query_lower in content_lower:
                score += 5.0
            else:
                # Add token overlap boost
                words_in_content = set(content_lower.split())
                overlap = len(query_words.intersection(words_in_content))
                score += overlap * 0.5

            item.rerank_score = round(score, 4)
            scored_candidates.append(item)

        # Sort descending by rerank_score and return top_k
        scored_candidates.sort(key=lambda x: x.rerank_score, reverse=True)
        return scored_candidates[:top_k]


class CrossEncoderRerankerClient(RerankerClient):
    """
    Production cross-encoder reranker leveraging a Text Embeddings Inference (TEI) compatible endpoint.
    Scores candidates in batch to respect latency budgets.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        model: str = "BAAI/bge-reranker-v2-m3",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._http_client = http_client

    async def rerank(
        self, query: str, candidates: list[ScoredMemoryItem], top_k: int = 5
    ) -> list[ScoredMemoryItem]:
        if not candidates:
            return []

        client = self._http_client or httpx.AsyncClient()
        close_client = self._http_client is None

        try:
            payload = {
                "model": self.model,
                "query": query,
                "texts": [c.content for c in candidates],
            }
            # Target HF Text Embeddings Inference (TEI) / Cohere compatible endpoint
            response = await client.post(
                f"{self.base_url}/rerank",
                json=payload,
                timeout=1.5,  # Strict latency budget per PRD
            )
            response.raise_for_status()
            results = response.json()

            # Assign scores back to candidates based on index
            for res in results:
                idx = res["index"]
                candidates[idx].rerank_score = float(res["score"])

            # Fallback for candidates missing scores
            for c in candidates:
                if not hasattr(c, "rerank_score"):
                    c.rerank_score = -999.0

            candidates.sort(key=lambda x: x.rerank_score, reverse=True)
            return candidates[:top_k]
        except Exception:
            # Fallback to base RRF if reranker fails to ensure fail-soft behavior
            for c in candidates:
                c.rerank_score = c.rrf_score
            candidates.sort(key=lambda x: x.rerank_score, reverse=True)
            return candidates[:top_k]
        finally:
            if close_client:
                await client.aclose()
