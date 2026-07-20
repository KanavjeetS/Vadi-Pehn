"""
FastAPI entry point for the standalone Safety Proxy service.
Implements: PRD §8 (Safety Guardrails & Pre-Filter Infrastructure), SD §4.3.
Enforces fail-closed classification across all turns.
"""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.abstractions import SafetyVerdict, SafetyVerdictCode
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


@app.post("/internal/v1/safety/check-input", response_model=SafetyResponseDto)
async def check_input_endpoint(request: CheckInputRequest) -> SafetyResponseDto:
    """
    Check child input before any LLM generation begins (SD §4.3).
    Enforces a strict 3.0-second timeout and returns `classifier_unavailable` on failure.
    """
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
        return SafetyResponseDto(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE, taxonomy_code="ERR_TIMEOUT")


@app.post("/internal/v1/safety/check-output", response_model=SafetyResponseDto)
async def check_output_endpoint(request: CheckOutputRequest) -> SafetyResponseDto:
    """
    Check draft LLM response before sending back to the child (SD §4.3).
    Enforces a strict 3.0-second timeout and returns `classifier_unavailable` on failure.
    """
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
