"""
Ollama Open-Source LLM Client for Vadi-Pehn Orchestration.
Integrates local open-source models (Llama-3.3, Qwen-2.5, Llama-3.2) via Ollama API.
Supports streaming responses and mock fallback for hermetic testing.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator
import httpx

from services.abstractions import LLMClient
logger = logging.getLogger("orchestration.ollama_client")


class OllamaLLMClient(LLMClient):
    """
    Production client for local open-source Ollama models.
    Default endpoint: http://localhost:11434 (configurable via env/settings).
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "llama3.3:latest",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str | list[str]:
        """
        Generate text completion using local Ollama model API.
        """
        # This client is for isolated local development only. Production generation
        # is routed through SafetyProxyLLMClient, where safety controls own the
        # model network boundary.
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()

                if not stream:
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                    return content
                else:
                    chunks: list[str] = []
                    for line in response.text.splitlines():
                        if line.strip():
                            parsed = json.loads(line)
                            chunk_text = parsed.get("message", {}).get("content", "")
                            if chunk_text:
                                chunks.append(chunk_text)
                    return chunks if chunks else ["[Ollama Stream Complete]"]

        except httpx.HTTPError as exc:
            logger.error("Ollama generation failed")
            raise RuntimeError("Local LLM provider unavailable") from exc

    async def stream(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream text token deltas in real-time.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", f"{self.ollama_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                continue
        except httpx.HTTPError as exc:
            logger.error("Ollama stream failed")
            raise RuntimeError("Local LLM provider unavailable") from exc
