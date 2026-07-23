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
from pydantic import BaseModel, Field

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.abstractions import SafetyVerdictCode
from services.config import require_internal_service_token, settings
from services.logging_config import configure_logging
from safety_proxy.actions import classify_input, classify_output

configure_logging("safety-proxy")

app = FastAPI(
    title="Vadi-Pehn Safety Proxy",
    description="NeMo Guardrails & Llama-Guard reverse proxy ensuring child-safe AI responses.",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "safety-proxy"}


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
        async with httpx.AsyncClient(timeout=3.0) as client:
            result = await asyncio.wait_for(
                classify_input(
                    message_text=request.message_text,
                    age_band=request.age_band,
                    tenant_id=request.tenant_id,
                    http_client=client,
                ),
                timeout=3.0,
            )
            # Dev bypass: classify_input catches its own connection errors and returns
            # CLASSIFIER_UNAVAILABLE as a value (not an exception). In dev mode, convert
            # this to SAFE so that generation can proceed while the GPU container is offline.
            # Production (is_dev=False) is unaffected — fail-closed invariant preserved.
            if (
                result.code == SafetyVerdictCode.CLASSIFIER_UNAVAILABLE
                and settings.safety_proxy.allow_dev_bypass
                and settings.is_dev
            ):
                return SafetyResponseDto(code=SafetyVerdictCode.SAFE, taxonomy_code=None)
            return SafetyResponseDto(code=result.code, taxonomy_code=result.taxonomy_code)
    except (asyncio.TimeoutError, Exception):
        if settings.safety_proxy.allow_dev_bypass and settings.is_dev:
            return SafetyResponseDto(code=SafetyVerdictCode.SAFE, taxonomy_code=None)
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
        async with httpx.AsyncClient(timeout=3.0) as client:
            result = await asyncio.wait_for(
                classify_output(
                    draft_reply_text=request.draft_reply_text,
                    tenant_id=request.tenant_id,
                    http_client=client,
                ),
                timeout=3.0,
            )
            # Same dev bypass logic as check-input: catch CLASSIFIER_UNAVAILABLE return value.
            if (
                result.code == SafetyVerdictCode.CLASSIFIER_UNAVAILABLE
                and settings.safety_proxy.allow_dev_bypass
                and settings.is_dev
            ):
                return SafetyResponseDto(code=SafetyVerdictCode.SAFE)
            return SafetyResponseDto(code=result.code)
    except (asyncio.TimeoutError, Exception):
        if settings.safety_proxy.allow_dev_bypass and settings.is_dev:
            return SafetyResponseDto(code=SafetyVerdictCode.SAFE)
        return SafetyResponseDto(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE)


@app.post("/internal/v1/llm/chat/completions")
async def proxy_llm(
    request: LLMProxyRequest, x_internal_service_token: str = Header(default="")
):
    """Proxy main-model calls to vLLM (primary) then Groq (fallback).

    Primary path: local vLLM / NVIDIA NIM container at VLLM_MAIN_URL.
    Fallback path: Groq Cloud llama-3.3-70b-versatile (sub-100ms, always available).
    Both paths return the same OpenAI-compatible JSON schema.
    """
    require_internal_service_token(x_internal_service_token)

    payload = request.model_dump()

    # ── Try primary: local vLLM / NVIDIA NIM ─────────────────────────────────
    vllm_upstream = f"{settings.vllm.main_url.rstrip('/')}/v1/chat/completions"
    vllm_payload = dict(payload)
    vllm_payload["model"] = settings.vllm.main_model
    vllm_headers: dict[str, str] = {}
    if settings.vllm.nvidia_api_key:
        vllm_headers["Authorization"] = f"Bearer {settings.vllm.nvidia_api_key}"

    try:
        async with httpx.AsyncClient(timeout=min(settings.vllm.main_timeout_seconds, 5.0)) as client:
            response = await client.post(vllm_upstream, json=vllm_payload, headers=vllm_headers)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, httpx.TimeoutException, RuntimeError):
        pass  # fall through to Groq

    # ── Fallback: Groq Cloud ──────────────────────────────────────────────────
    groq_api_key = settings.groq.api_key if hasattr(settings, "groq") else ""
    if groq_api_key:
        groq_upstream = "https://api.groq.com/openai/v1/chat/completions"
        groq_payload = dict(payload)
        groq_payload["model"] = (
            settings.groq.llm_model
            if hasattr(settings, "groq") and settings.groq.llm_model
            else "llama-3.3-70b-versatile"
        )
        # Groq does not support stream=True in JSON body this way; use False for non-stream
        groq_payload.pop("stream", None)
        groq_headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    groq_upstream, json=groq_payload, headers=groq_headers
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, httpx.TimeoutException, RuntimeError):
            pass  # fall through to stub

    # ── Last-resort stub (dev only) ───────────────────────────────────────────
    if settings.is_dev:
        return {
            "id": "chatcmpl-stub",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Haan bolo, main sun raha hoon! Kya baat hai?",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
    raise HTTPException(status_code=503, detail="LLM upstream unavailable")
