"""HTTP LLM client whose only upstream is the Safety Proxy."""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from services.abstractions import LLMClient
from services.config import settings


class SafetyProxyLLMClient(LLMClient):
    """Call the main model through the isolated Safety Proxy network boundary."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.safety_proxy.url).rstrip("/")

    async def generate(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str | list[str]:
        if stream:
            return [
                chunk
                async for chunk in self.stream(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            ]

        payload = await self._request(messages, max_tokens, temperature, stream=False)
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM returned no choices")
        return str(choices[0].get("message", {}).get("content", ""))

    async def stream(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        timeout = httpx.Timeout(settings.vllm.main_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/internal/v1/llm/chat/completions",
                json={
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
                headers=self._headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        yield str(delta)

    async def _request(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        *,
        stream: bool,
    ) -> dict:
        async with httpx.AsyncClient(
            timeout=settings.vllm.main_timeout_seconds
        ) as client:
            response = await client.post(
                f"{self.base_url}/internal/v1/llm/chat/completions",
                json={
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": stream,
                },
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    @property
    def _headers(self) -> dict[str, str]:
        return (
            {"X-Internal-Service-Token": settings.internal_service_token}
            if settings.internal_service_token
            else {}
        )
