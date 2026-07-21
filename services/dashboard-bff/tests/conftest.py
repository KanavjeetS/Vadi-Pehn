from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "api-gateway", "src")
)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from dashboard_bff import main as dashboard_main


class FakeDashboardRepository:
    async def learners(self, tenant_id, guardian_id):
        return [
            {
                "learner_id": uuid4(),
                "display_name": "Learner Alex",
                "age_band": 2,
                "active_relationships_count": 2,
                "last_session_at": datetime.now(timezone.utc),
            }
        ]

    async def learner_count(self, tenant_id):
        return 150


@pytest.fixture(autouse=True)
def dashboard_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_json(url: str, **_: object) -> dict:
        if "consent/summary" in url:
            return {
                "conversation_storage": True,
                "document_ingestion": True,
                "voice_recording": True,
                "career_introductions": True,
            }
        now = datetime.now(timezone.utc).isoformat()
        return {
            "incidents": [
                {
                    "incident_id": "inc_test_01",
                    "learner_id": str(uuid4()),
                    "category": "unsafe_self_harm",
                    "created_at": now,
                    "sla_deadline": now,
                    "is_breached": False,
                    "acknowledged_at": None,
                }
            ]
        }

    monkeypatch.setattr(dashboard_main, "dashboard_repo", FakeDashboardRepository())
    monkeypatch.setattr(dashboard_main, "_get_json", get_json)
