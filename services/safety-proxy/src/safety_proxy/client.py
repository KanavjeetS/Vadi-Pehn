"""
SafetyClient implementation for Orchestration Service -> Safety Proxy network path.
Implements: PRD §8 (Safety Gateway), SD §4.3 (API Contracts).
Child Safety Non-Negotiable #1, #2: Network-level safety proxy invocation with fail-closed timeout.
"""

from __future__ import annotations

from uuid import UUID

import httpx

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from services.abstractions import SafetyClient, SafetyVerdict, SafetyVerdictCode
from services.config import settings


class NeMoSafetyClient(SafetyClient):
    """
    HTTP client wrapping the network path to the standalone Safety Proxy service.
    Called by Orchestration before and after every LLM generation.
    Enforces 3.0-second timeout. On error/timeout, returns `SafetyVerdict.unavailable()`.
    """

    def __init__(
        self,
        base_url: str = settings.safety_proxy.url,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = http_client

    @property
    def _headers(self) -> dict[str, str]:
        return (
            {"X-Internal-Service-Token": settings.internal_service_token}
            if settings.internal_service_token
            else {}
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=3.0)

    async def check_input(
        self,
        *,
        learner_id: UUID,
        message_text: str,
        age_band: int = 2,
        tenant_id: UUID | None = None,
    ) -> SafetyVerdict:
        """
        Check learner input via POST /internal/v1/safety/check-input.
        Fail-closed: returns `SafetyVerdict.unavailable()` on network error or timeout.
        """
        client = await self._get_client()
        try:
            response = await client.post(
                f"{self.base_url}/internal/v1/safety/check-input",
                json={
                    "learner_id": str(learner_id),
                    "message_text": message_text,
                    "age_band": age_band,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
                headers=self._headers,
                timeout=3.0,
            )
            response.raise_for_status()
            data = response.json()
            code_str = data.get("code") or data.get("verdict", "classifier_unavailable")
            return SafetyVerdict(
                code=SafetyVerdictCode(code_str),
                taxonomy_code=data.get("taxonomy_code"),
            )
        except (
            httpx.TimeoutException,
            httpx.RequestError,
            httpx.HTTPStatusError,
            KeyError,
            ValueError,
        ):
            return SafetyVerdict.unavailable()

    async def check_output(
        self,
        *,
        learner_id: UUID,
        draft_reply_text: str,
        tenant_id: UUID | None = None,
    ) -> SafetyVerdict:
        """
        Check draft LLM output via POST /internal/v1/safety/check-output.
        Fail-closed: returns `SafetyVerdict.unavailable()` on network error or timeout.
        """
        client = await self._get_client()
        try:
            response = await client.post(
                f"{self.base_url}/internal/v1/safety/check-output",
                json={
                    "learner_id": str(learner_id),
                    "draft_reply_text": draft_reply_text,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
                headers=self._headers,
                timeout=3.0,
            )
            response.raise_for_status()
            data = response.json()
            code_str = data.get("code") or data.get("verdict", "classifier_unavailable")
            return SafetyVerdict(code=SafetyVerdictCode(code_str))
        except (
            httpx.TimeoutException,
            httpx.RequestError,
            httpx.HTTPStatusError,
            KeyError,
            ValueError,
        ):
            return SafetyVerdict.unavailable()
