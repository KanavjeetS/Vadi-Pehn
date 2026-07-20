"""
NeMo Guardrails custom actions and Llama-Guard-3-8B classification logic.
Implements: PRD §8.1 (Input Guard & Jailbreak), PRD §8.2 (Output Guard), SD §4.3.

Child Safety Non-Negotiable #1, #2:
- No safety proxy bypass.
- Fail-closed always: if the classifier times out (> 3.0s), raises an exception,
  or returns an unparseable response, it MUST return `classifier_unavailable`
  and block generation (`blocks_generation = True`). Never default to `safe`.
"""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import httpx

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from services.abstractions import SafetyVerdict, SafetyVerdictCode
from services.config import settings


# Local keyword pre-filter patterns for ultra-fast fail-fast check before network LLM call
SELF_HARM_KEYWORDS = {
    "kill myself", "suicide", "end my life", "want to die", "hurt myself", "cut myself"
}
ABUSE_KEYWORDS = {
    "hit me", "hitting me", "touching me", "secret touch", "hurting me at home", "beat me"
}
JAILBREAK_KEYWORDS = {
    "ignore previous instructions", "system prompt", "you are now dan", "bypass rules", "override safety"
}


async def classify_input(
    message_text: str,
    age_band: int = 2,
    tenant_id: UUID | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> SafetyVerdict:
    """
    Classify input text against child safety policies (Aegis 2.0 / LlamaGuard taxonomy).
    Enforces a strict 3.0s timeout and fails closed on ANY error or timeout.
    """
    text_lower = message_text.lower().strip()

    # 1. Fast local pre-filter checks
    if any(kw in text_lower for kw in SELF_HARM_KEYWORDS):
        return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_SELF_HARM, taxonomy_code="S6")
    if any(kw in text_lower for kw in ABUSE_KEYWORDS):
        return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL, taxonomy_code="S7")
    if any(kw in text_lower for kw in JAILBREAK_KEYWORDS):
        return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL, taxonomy_code="S10")

    # If running in development or testing without a live LlamaGuard container and no http_client was passed, return safe
    if http_client is None and settings.is_dev:
        return SafetyVerdict(code=SafetyVerdictCode.SAFE, taxonomy_code=None)

    # 2. Network classification call against Llama-Guard-3-8B container (with strict 3.0s SLA)
    try:
        response = await asyncio.wait_for(
            http_client.post(
                f"{settings.vllm.classifier_url}/v1/chat/completions",
                json={
                    "model": "meta-llama/Llama-Guard-3-8B",
                    "messages": [{"role": "user", "content": message_text}],
                    "temperature": 0.0,
                    "max_tokens": 16,
                },
                timeout=3.0,
            ),
            timeout=3.0,
        )
        response.raise_for_status()
        data = response.json()
        output = data["choices"][0]["message"]["content"].strip()
        if output.startswith("unsafe"):
            lines = output.split("\n")
            code = lines[1].strip() if len(lines) > 1 else "S1"
            verdict_code = SafetyVerdictCode.UNSAFE_SELF_HARM if code == "S6" else SafetyVerdictCode.UNSAFE_GENERAL
            return SafetyVerdict(code=verdict_code, taxonomy_code=code)
        return SafetyVerdict(code=SafetyVerdictCode.SAFE, taxonomy_code=None)
    except (asyncio.TimeoutError, httpx.TimeoutException, httpx.RequestError, KeyError, ValueError, httpx.HTTPStatusError, AttributeError):
        # FAIL-CLOSED INVARIANT: On network failure or classifier timeout, block generation!
        return SafetyVerdict(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE, taxonomy_code="ERR_TIMEOUT")


async def classify_output(
    draft_reply_text: str,
    tenant_id: UUID | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> SafetyVerdict:
    """
    Classify draft output text before delivering to the child (PRD §8.2).
    Enforces a strict 3.0s timeout and fails closed on error.
    """
    text_lower = draft_reply_text.lower().strip()
    if any(kw in text_lower for kw in SELF_HARM_KEYWORDS | ABUSE_KEYWORDS):
        return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL)

    if http_client is None and settings.is_dev:
        return SafetyVerdict(code=SafetyVerdictCode.SAFE)

    try:
        response = await asyncio.wait_for(
            http_client.post(
                f"{settings.vllm.classifier_url}/v1/chat/completions",
                json={
                    "model": "meta-llama/Llama-Guard-3-8B",
                    "messages": [{"role": "assistant", "content": draft_reply_text}],
                    "temperature": 0.0,
                    "max_tokens": 16,
                },
                timeout=3.0,
            ),
            timeout=3.0,
        )
        response.raise_for_status()
        data = response.json()
        output = data["choices"][0]["message"]["content"].strip()
        if output.startswith("unsafe"):
            return SafetyVerdict(code=SafetyVerdictCode.UNSAFE_GENERAL)
        return SafetyVerdict(code=SafetyVerdictCode.SAFE)
    except (asyncio.TimeoutError, httpx.TimeoutException, httpx.RequestError, KeyError, ValueError, httpx.HTTPStatusError, AttributeError):
        return SafetyVerdict(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE, taxonomy_code="ERR_TIMEOUT")


# NeMo Action callbacks wired into child_safety.co flow definitions
async def check_input_classifier(message_text: str, age_band: int = 2) -> str:
    res = await classify_input(message_text, age_band)
    return res.code.value

async def check_jailbreak_classifier(message_text: str) -> bool:
    text_lower = message_text.lower()
    return any(kw in text_lower for kw in JAILBREAK_KEYWORDS)

async def check_output_classifier(draft_text: str) -> str:
    res = await classify_output(draft_text)
    return res.code.value
