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

    async def session_count(self, tenant_id, learner_ids=None):
        return 5

    async def learner_streak(self, tenant_id, guardian_id=None):
        return "5 days"

    async def weekly_engagement(self, tenant_id, guardian_id=None):
        return "2h 52m"

    async def discrepancy_count(self, tenant_id):
        return 0

    async def total_sessions_count(self, tenant_id=None):
        return 10

    async def top_growing_skill(self, tenant_id, learner_ids=None):
        return "World exposure"

    async def session_trends(self, tenant_id, guardian_id=None):
        return [
            {"day": "Mon", "minutes": 18},
            {"day": "Tue", "minutes": 24},
            {"day": "Wed", "minutes": 12},
            {"day": "Thu", "minutes": 28},
            {"day": "Fri", "minutes": 20},
            {"day": "Sat", "minutes": 36},
            {"day": "Sun", "minutes": 22},
        ]

    async def topic_distribution(self, tenant_id, learner_ids=None):
        return [
            {"topic": "Curious", "count": 9, "percentage": 45.0},
            {"topic": "Calm", "count": 6, "percentage": 30.0},
            {"topic": "STEM & Robotics", "count": 3, "percentage": 15.0},
            {"topic": "Creative Arts", "count": 2, "percentage": 10.0},
        ]



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
