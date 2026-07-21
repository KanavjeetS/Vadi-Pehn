"""Remote streaming client for the production orchestration service."""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from services.config import settings


class RemoteOrchestrationClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.voice.orchestration_url).rstrip("/")

    async def stream_reply(self, state) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(
            timeout=settings.vllm.main_timeout_seconds
        ) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/internal/v1/orchestration/stream",
                json={
                    "session_id": state.session_id,
                    "tenant_id": state.tenant_id,
                    "learner_id": state.learner_id,
                    "age_band": state.age_band,
                    "message_text": state.message_text,
                    "language": state.language_detected,
                },
                headers=(
                    {"X-Internal-Service-Token": settings.internal_service_token}
                    if settings.internal_service_token
                    else {}
                ),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        delta = json.loads(data).get("delta")
                    except json.JSONDecodeError:
                        continue
                    if delta:
                        yield str(delta)
