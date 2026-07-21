from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from api_gateway import main as api_main
from api_gateway.identity_store import InMemoryIdentityStore


@pytest.fixture(autouse=True)
def fake_internal_services(monkeypatch: pytest.MonkeyPatch) -> None:
    async def post_json(url: str, payload: dict, **_: object) -> dict:
        if "orchestration" in url:
            return {
                "session_id": payload["session_id"],
                "turn_id": "test-turn",
                "final_reply": "Test orchestration reply",
                "safety_verdict_output": {"code": "safe"},
            }
        if "governance" in url:
            return {
                "learner_id": payload.get("learner_id"),
                "conversation_storage": True,
            }
        if "ingestion" in url:
            return {
                "document_id": "00000000-0000-0000-0000-000000000010",
                "tenant_id": payload["tenant_id"],
                "learner_id": payload["learner_id"],
                "student_name": "Test Learner",
                "overall_grade": "A",
                "subjects": {},
                "ocr_confidence": 0.94,
                "redaction_verified": True,
                "requires_discrepancy_review": False,
                "discrepancy_reasons": [],
            }
        return {"session_id": payload["session_id"], "reply_text": "Test voice reply"}

    monkeypatch.setattr(api_main, "_post_json", post_json)
    monkeypatch.setattr(api_main, "identity_store", InMemoryIdentityStore())
