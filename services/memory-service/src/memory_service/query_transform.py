"""
Query Transformation Client (`services/memory-service/query_transform.py`).
Implements query rewriting and multi-query expansion with a strict latency fallback.
"""

from __future__ import annotations

import asyncio
import httpx

from memory_service.abstractions import QueryTransformer


class MockQueryTransformer(QueryTransformer):
    """Deterministic mock transformer for testing."""
    
    async def transform(self, query: str) -> list[str]:
        return [query, f"{query} expanded"]


class LLMQueryTransformer(QueryTransformer):
    """
    Production query transformer using an LLM endpoint.
    Applies a strict latency fallback (e.g., 1.0 second limit).
    If the LLM fails or times out, returns the original query.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        timeout_seconds: float = 1.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    async def transform(self, query: str) -> list[str]:
        client = self._http_client or httpx.AsyncClient()
        close_client = self._http_client is None

        prompt = (
            "You are a search query expansion expert. "
            f"Rewrite and expand the following query into 2 variations separated by newlines. Query: {query}"
        )

        try:
            # We use asyncio.wait_for as a strict latency fallback.
            # (httpx also has timeouts, but asyncio.wait_for is an extra safeguard).
            response = await asyncio.wait_for(
                client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=self.timeout_seconds,
                ),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            expanded_text = data.get("response", "")
            
            # Split by newline and clean up
            queries = [q.strip() for q in expanded_text.split('\n') if q.strip()]
            
            if not queries:
                return [query]
                
            # Add original query if not present
            if query not in queries:
                queries.insert(0, query)
                
            return queries[:3] # Keep original + up to 2 expansions
            
        except (asyncio.TimeoutError, httpx.RequestError, Exception):
            # Strict fallback: if it takes too long or fails, just use original query
            return [query]
        finally:
            if close_client:
                await client.aclose()
