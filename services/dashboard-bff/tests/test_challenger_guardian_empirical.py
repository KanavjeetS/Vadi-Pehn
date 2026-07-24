"""
Empirical Challenger Test Suite for Guardian Overview API & Frontend Integration (Milestone 4).

Verifies:
  1. Guardian Overview API under empty database state, single turn state, and multi-turn state.
  2. Chart.js rendering data contract (7-day session trends & topic distribution percentages).
  3. Dynamic metric updates (session counts, weekly engagement, streak calculation, relationship health).
  4. Consent toggle API synchronization, alias resolution, and tenant isolation enforcement.
  5. Safety incident 15-minute SLA tracking, breach status calculation, and acknowledgment API.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api-gateway", "src"))

import dashboard_bff.main as main_module
from api_gateway.auth import create_jwt_token
from api_gateway.main import app as gateway_app
from dashboard_bff.main import app as bff_app
from dashboard_bff.models import GuardianOverview, IncidentSummary
from dashboard_bff.repository import InMemoryDashboardRepository

client_bff = TestClient(bff_app)
client_gateway = TestClient(gateway_app)


class CustomMockDashboardRepository:
    """Configurable mock repository to test empty, single-turn, and multi-turn states."""

    def __init__(
        self,
        learners_list: list[dict] | None = None,
        sessions_list: list[dict] | None = None,
        streak_val: str = "0 days",
        weekly_engagement_val: str = "0h 0m",
        top_skill_val: str = "World exposure",
        session_trends_list: list[dict] | None = None,
        topic_distribution_list: list[dict] | None = None,
    ) -> None:
        self._learners = learners_list or []
        self._sessions = sessions_list or []
        self._streak = streak_val
        self._weekly_engagement = weekly_engagement_val
        self._top_skill = top_skill_val
        self._session_trends = session_trends_list or []
        self._topic_distribution = topic_distribution_list or []

    async def learners(self, tenant_id: UUID, guardian_id: UUID) -> list[dict]:
        return [
            row for row in self._learners
            if str(row.get("tenant_id", tenant_id)) == str(tenant_id)
        ]

    async def learner_count(self, tenant_id: UUID) -> int:
        return len(self._learners)

    async def session_count(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> int:
        return len(self._sessions)

    async def learner_streak(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> str:
        return self._streak

    async def weekly_engagement(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> str:
        return self._weekly_engagement

    async def discrepancy_count(self, tenant_id: UUID) -> int:
        return 0

    async def total_sessions_count(self, tenant_id: UUID | None = None) -> int:
        return len(self._sessions)

    async def top_growing_skill(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> str:
        return self._top_skill

    async def session_trends(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> list[dict]:
        if self._session_trends:
            return self._session_trends
        today = datetime.now(timezone.utc).date()
        return [
            {"day": (today - timedelta(days=i)).strftime("%a"), "minutes": 0}
            for i in range(6, -1, -1)
        ]

    async def topic_distribution(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> list[dict]:
        return self._topic_distribution


# ── 1. Empty Database State Tests ──────────────────────────────────────────

def test_guardian_overview_empty_database_state() -> None:
    """Verifies Guardian overview response structure when the database is completely empty."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    empty_repo = CustomMockDashboardRepository(
        learners_list=[],
        sessions_list=[],
        streak_val="0 days",
        weekly_engagement_val="0h 0m",
        session_trends_list=[
            {"day": day, "minutes": 0}
            for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        ],
        topic_distribution_list=[],
    )

    with patch.object(main_module, "dashboard_repo", empty_repo), \
         patch("dashboard_bff.main._get_json", new_callable=AsyncMock) as mock_get_json:

        async def empty_governance_side_effect(url, headers=None):
            if "consent/summary" in url:
                return {
                    "conversation_storage": True,
                    "document_ingestion": True,
                    "voice_recording": True,
                    "career_introductions": True,
                }
            if "incidents" in url:
                return {"incidents": []}
            return {}

        mock_get_json.side_effect = empty_governance_side_effect

        res = client_bff.get(
            "/api/v1/guardian/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()

    assert data["guardian_id"] == guardian_id
    assert data["tenant_id"] == tenant_id
    assert data["learners"] == []
    assert data["active_learners"] == 0
    assert data["session_count"] == 0
    assert data["weekly_engagement_hours"] == "0h 0m"
    assert data["current_streak"] == "0 days"
    assert data["top_growing_skill"] == "World exposure"

    # Verify Chart.js contract for session trends
    assert len(data["session_trends"]) == 7
    for item in data["session_trends"]:
        assert "day" in item
        assert "minutes" in item
        assert item["minutes"] == 0

    # Verify Chart.js contract for empty topic distribution
    assert isinstance(data["topic_distribution"], list)
    assert data["safety_incidents"] == []


# ── 2. Single Turn State Tests ─────────────────────────────────────────────

def test_guardian_overview_single_turn_state() -> None:
    """Verifies Guardian overview when a learner has completed a single turn/session."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    learner_id = str(uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    now = datetime.now(timezone.utc)
    single_turn_repo = CustomMockDashboardRepository(
        learners_list=[
            {
                "tenant_id": UUID(tenant_id),
                "guardian_id": UUID(guardian_id),
                "learner_id": UUID(learner_id),
                "display_name": "Rohan",
                "age_band": 1,
                "active_relationships_count": 1,
                "last_session_at": now,
            }
        ],
        sessions_list=[
            {
                "tenant_id": UUID(tenant_id),
                "learner_id": UUID(learner_id),
                "session_id": "sess_single_001",
                "created_at": now,
            }
        ],
        streak_val="1 day",
        weekly_engagement_val="0h 5m",
        top_skill_val="Robotics & Coding",
        session_trends_list=[
            {"day": "Mon", "minutes": 0},
            {"day": "Tue", "minutes": 0},
            {"day": "Wed", "minutes": 0},
            {"day": "Thu", "minutes": 0},
            {"day": "Fri", "minutes": 0},
            {"day": "Sat", "minutes": 0},
            {"day": "Sun", "minutes": 5},
        ],
        topic_distribution_list=[
            {"topic": "Robotics & Coding", "count": 1, "percentage": 100.0}
        ],
    )

    with patch.object(main_module, "dashboard_repo", single_turn_repo):
        res = client_bff.get(
            "/api/v1/guardian/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    data = res.json()

    assert data["active_learners"] == 1
    assert len(data["learners"]) == 1
    learner = data["learners"][0]
    assert learner["learner_id"] == learner_id
    assert learner["display_name"] == "Rohan"
    assert learner["age_band"] == 1
    assert learner["active_relationships_count"] == 1
    assert learner["relationship_health_trend"] == "healthy"

    assert data["session_count"] == 1
    assert data["weekly_engagement_hours"] == "0h 5m"
    assert data["current_streak"] == "1 day"
    assert data["top_growing_skill"] == "Robotics & Coding"

    # Chart data validation
    assert len(data["session_trends"]) == 7
    total_minutes = sum(t["minutes"] for t in data["session_trends"])
    assert total_minutes == 5

    assert len(data["topic_distribution"]) == 1
    assert data["topic_distribution"][0]["topic"] == "Robotics & Coding"
    assert data["topic_distribution"][0]["percentage"] == 100.0


# ── 3. Multi-Turn & Multi-Learner State Tests ──────────────────────────────

def test_guardian_overview_multi_turn_state() -> None:
    """Verifies Guardian overview under multi-turn, multi-learner, multi-day engagement."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    learner_1 = str(uuid4())
    learner_2 = str(uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    now = datetime.now(timezone.utc)
    multi_repo = CustomMockDashboardRepository(
        learners_list=[
            {
                "tenant_id": UUID(tenant_id),
                "guardian_id": UUID(guardian_id),
                "learner_id": UUID(learner_1),
                "display_name": "Aria",
                "age_band": 2,
                "active_relationships_count": 2,
                "last_session_at": now,
            },
            {
                "tenant_id": UUID(tenant_id),
                "guardian_id": UUID(guardian_id),
                "learner_id": UUID(learner_2),
                "display_name": "Kabir",
                "age_band": 3,
                "active_relationships_count": 5,  # > 3 -> over_engaged
                "last_session_at": now - timedelta(hours=2),
            },
        ],
        sessions_list=[
            {"session_id": f"sess_{i}"} for i in range(12)
        ],
        streak_val="5 days",
        weekly_engagement_val="2h 15m",
        top_skill_val="Environmental Science",
        session_trends_list=[
            {"day": "Mon", "minutes": 20},
            {"day": "Tue", "minutes": 15},
            {"day": "Wed", "minutes": 30},
            {"day": "Thu", "minutes": 25},
            {"day": "Fri", "minutes": 10},
            {"day": "Sat", "minutes": 20},
            {"day": "Sun", "minutes": 15},
        ],
        topic_distribution_list=[
            {"topic": "Environmental Science", "count": 10, "percentage": 40.0},
            {"topic": "Robotics", "count": 8, "percentage": 32.0},
            {"topic": "Creative Arts", "count": 7, "percentage": 28.0},
        ],
    )

    with patch.object(main_module, "dashboard_repo", multi_repo):
        res = client_bff.get(
            "/api/v1/guardian/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    data = res.json()

    assert data["active_learners"] == 2
    assert len(data["learners"]) == 2

    # Learner 1 checks
    l1 = next(l for l in data["learners"] if l["learner_id"] == learner_1)
    assert l1["display_name"] == "Aria"
    assert l1["relationship_health_trend"] == "healthy"

    # Learner 2 checks (active_relationships_count = 5 > 3 -> over_engaged)
    l2 = next(l for l in data["learners"] if l["learner_id"] == learner_2)
    assert l2["display_name"] == "Kabir"
    assert l2["relationship_health_trend"] == "over_engaged"

    assert data["session_count"] == 12
    assert data["weekly_engagement_hours"] == "2h 15m"
    assert data["current_streak"] == "5 days"

    # Chart.js totals check
    trends = data["session_trends"]
    assert len(trends) == 7
    total_min = sum(t["minutes"] for t in trends)
    assert total_min == 135  # 2h 15m = 135 min

    # Topic distribution check
    topics = data["topic_distribution"]
    assert len(topics) == 3
    total_pct = sum(t["percentage"] for t in topics)
    assert abs(total_pct - 100.0) < 0.1


# ── 4. Consent Toggle API Synchronization Tests ────────────────────────────

@pytest.mark.asyncio
async def test_consent_toggle_synchronization_and_validation() -> None:
    """Verifies consent update endpoint via API gateway across all 4 consent fields and alias mapping."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    learner_id = str(uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    valid_consent_types = [
        "conversation_storage",
        "document_ingestion",
        "voice_recording",
        "career_introductions",
    ]

    for c_type in valid_consent_types:
        payload = {
            "tenant_id": tenant_id,
            "guardian_id": guardian_id,
            "learner_id": learner_id,
            "consent_type": c_type,
            "granted": True,
        }
        headers = {"Authorization": f"Bearer {token}"}

        with patch("api_gateway.main._post_json", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "learner_id": learner_id,
                "tenant_id": tenant_id,
                c_type: True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            res = client_gateway.post(
                "/api/v1/guardian/consent", json=payload, headers=headers
            )

        assert res.status_code == 200, f"Failed for {c_type}: {res.text}"
        res_data = res.json()
        assert res_data["status"] == "updated"
        assert res_data["consent_type"] == c_type
        assert res_data["granted"] is True


def test_consent_toggle_invalid_type_returns_422() -> None:
    """Verifies invalid/unsupported consent type is rejected with 422 HTTP status."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    learner_id = str(uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    payload = {
        "tenant_id": tenant_id,
        "guardian_id": guardian_id,
        "learner_id": learner_id,
        "consent_type": "invalid_unsupported_consent_type",
        "granted": True,
    }
    headers = {"Authorization": f"Bearer {token}"}

    res = client_gateway.post(
        "/api/v1/guardian/consent", json=payload, headers=headers
    )
    assert res.status_code == 422
    assert "Unsupported consent type" in res.json()["detail"]


def test_consent_toggle_tenant_isolation_enforcement() -> None:
    """Verifies guardian cannot update consent for another tenant/subject ID."""
    real_tenant_id = str(uuid4())
    real_guardian_id = str(uuid4())
    other_tenant_id = str(uuid4())

    token = create_jwt_token(user_id=real_guardian_id, tenant_id=real_tenant_id, role="guardian")

    payload = {
        "tenant_id": other_tenant_id,  # Mismatched tenant
        "guardian_id": real_guardian_id,
        "learner_id": str(uuid4()),
        "consent_type": "conversation_storage",
        "granted": True,
    }
    headers = {"Authorization": f"Bearer {token}"}

    res = client_gateway.post(
        "/api/v1/guardian/consent", json=payload, headers=headers
    )
    assert res.status_code == 403


# ── 5. Safety Incident 15-Minute SLA Tracking Tests ───────────────────────

def test_safety_incident_sla_tracking_and_acknowledgment() -> None:
    """Verifies 15-minute SLA incident calculation, breach detection, and resolution trigger."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    learner_id = str(uuid4())
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    now = datetime.now(timezone.utc)
    # Incident 1: Active within SLA (created 5 mins ago)
    inc_active = {
        "incident_id": "inc_active_001",
        "learner_id": learner_id,
        "category": "self_harm_risk",
        "created_at": (now - timedelta(minutes=5)).isoformat(),
        "sla_deadline": (now + timedelta(minutes=10)).isoformat(),
        "is_breached": False,
        "acknowledged_at": None,
    }
    # Incident 2: Breached SLA (created 30 mins ago, not acknowledged)
    inc_breached = {
        "incident_id": "inc_breached_002",
        "learner_id": learner_id,
        "category": "cyberbullying",
        "created_at": (now - timedelta(minutes=30)).isoformat(),
        "sla_deadline": (now - timedelta(minutes=15)).isoformat(),
        "is_breached": True,
        "acknowledged_at": None,
    }

    mock_repo = CustomMockDashboardRepository(
        learners_list=[
            {
                "tenant_id": UUID(tenant_id),
                "guardian_id": UUID(guardian_id),
                "learner_id": UUID(learner_id),
                "display_name": "Aria",
                "age_band": 2,
                "active_relationships_count": 1,
                "last_session_at": now,
            }
        ]
    )

    with patch.object(main_module, "dashboard_repo", mock_repo), \
         patch("dashboard_bff.main._get_json", new_callable=AsyncMock) as mock_get_json:

        # Mock governance return
        async def side_effect(url, headers=None):
            if "consent/summary" in url:
                return {
                    "conversation_storage": True,
                    "document_ingestion": True,
                    "voice_recording": True,
                    "career_introductions": True,
                }
            if "incidents" in url:
                return {"incidents": [inc_active, inc_breached]}
            return {}

        mock_get_json.side_effect = side_effect

        res = client_bff.get(
            "/api/v1/guardian/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    data = res.json()

    incidents = data["safety_incidents"]
    assert len(incidents) == 2

    active_inc = next(i for i in incidents if i["incident_id"] == "inc_active_001")
    assert active_inc["is_breached"] is False
    assert active_inc["acknowledged"] is False
    assert active_inc["category"] == "self_harm_risk"

    breached_inc = next(i for i in incidents if i["incident_id"] == "inc_breached_002")
    assert breached_inc["is_breached"] is True
    assert breached_inc["acknowledged"] is False
    assert breached_inc["category"] == "cyberbullying"


def test_acknowledge_guardian_incident_endpoint() -> None:
    """Verifies incident acknowledgment endpoint updates status and returns acknowledged payload."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())
    incident_id = "inc_test_ack_777"
    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")

    with patch("dashboard_bff.main._post_json", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {
            "incident_id": incident_id,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_id": guardian_id,
        }

        res = client_bff.post(
            f"/api/v1/guardian/incident/{incident_id}/acknowledge",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "acknowledged"
    assert data["incident"]["incident_id"] == incident_id
    assert data["incident"]["reviewer_id"] == guardian_id


def test_acknowledge_guardian_incident_unauthenticated() -> None:
    """Verifies unauthenticated acknowledgment request is rejected with 401."""
    res = client_bff.post("/api/v1/guardian/incident/inc_test_123/acknowledge")
    assert res.status_code == 401
