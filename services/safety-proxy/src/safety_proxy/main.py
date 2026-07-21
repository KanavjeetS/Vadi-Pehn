"""
FastAPI entry point for the standalone Safety Proxy service.
Implements: PRD §8 (Safety Guardrails & Pre-Filter Infrastructure), SD §4.3.
Enforces fail-closed classification across all turns.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.abstractions import SafetyVerdictCode
from services.config import require_internal_service_token, settings
from safety_proxy.actions import classify_input, classify_output

app = FastAPI(
    title="Vadi-Pehn Safety Proxy",
    description="NeMo Guardrails & Llama-Guard reverse proxy ensuring child-safe AI responses.",
    version="0.1.0",
)


class CheckInputRequest(BaseModel):
    learner_id: UUID
    message_text: str
    age_band: int = Field(default=2, ge=1, le=3)
    tenant_id: UUID | None = None


class CheckOutputRequest(BaseModel):
    learner_id: UUID
    draft_reply_text: str
    tenant_id: UUID | None = None


class SafetyResponseDto(BaseModel):
    code: SafetyVerdictCode
    taxonomy_code: str | None = None


class LLMProxyRequest(BaseModel):
    messages: list[dict[str, str]]
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False


@app.post("/internal/v1/safety/check-input", response_model=SafetyResponseDto)
async def check_input_endpoint(
    request: CheckInputRequest, x_internal_service_token: str = Header(default="")
) -> SafetyResponseDto:
    """
    Check child input before any LLM generation begins (SD §4.3).
    Enforces a strict 3.0-second timeout and returns `classifier_unavailable` on failure.
    """
    require_internal_service_token(x_internal_service_token)
    try:
        result = await asyncio.wait_for(
            classify_input(
                message_text=request.message_text,
                age_band=request.age_band,
                tenant_id=request.tenant_id,
            ),
            timeout=3.0,
        )
        return SafetyResponseDto(code=result.code, taxonomy_code=result.taxonomy_code)
    except (asyncio.TimeoutError, Exception):
        # Fail-closed invariant
        return SafetyResponseDto(
            code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE, taxonomy_code="ERR_TIMEOUT"
        )


@app.post("/internal/v1/safety/check-output", response_model=SafetyResponseDto)
async def check_output_endpoint(
    request: CheckOutputRequest, x_internal_service_token: str = Header(default="")
) -> SafetyResponseDto:
    """
    Check draft LLM response before sending back to the child (SD §4.3).
    Enforces a strict 3.0-second timeout and returns `classifier_unavailable` on failure.
    """
    require_internal_service_token(x_internal_service_token)
    try:
        result = await asyncio.wait_for(
            classify_output(
                draft_reply_text=request.draft_reply_text,
                tenant_id=request.tenant_id,
            ),
            timeout=3.0,
        )
        return SafetyResponseDto(code=result.code)
    except (asyncio.TimeoutError, Exception):
        return SafetyResponseDto(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE)


@app.post("/internal/v1/llm/chat/completions")
async def proxy_llm(
    request: LLMProxyRequest, x_internal_service_token: str = Header(default="")
):
    """Proxy main-model calls from orchestration to the private vLLM network."""
    require_internal_service_token(x_internal_service_token)
    upstream = f"{settings.vllm.main_url.rstrip('/')}/v1/chat/completions"
    payload = request.model_dump()
    try:
        client = httpx.AsyncClient(timeout=settings.vllm.main_timeout_seconds)
        if request.stream:
            request_context = client.stream("POST", upstream, json=payload)
            upstream_response = await request_context.__aenter__()
            upstream_response.raise_for_status()

            async def events():
                try:
                    async for line in upstream_response.aiter_lines():
                        if line:
                            yield f"{line}\n\n"
                finally:
                    await upstream_response.aclose()
                    await client.aclose()

            return StreamingResponse(events(), media_type="text/event-stream")

        response = await client.post(upstream, json=payload)
        await client.aclose()
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="LLM upstream unavailable") from exc
