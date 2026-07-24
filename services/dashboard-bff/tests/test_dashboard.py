"""
Unit and Integration Tests for Guardian Dashboard BFF (Phase 8).
Verifies:
  1. Guardian surface overview & RLS scoping headers
  2. Admin incident triage overview
  3. Dynamic observability metrics & security access control
"""

from __future__ import annotations

import sys
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from dashboard_bff.main import app
from api_gateway.auth import create_jwt_token

client = TestClient(app)


def test_health_check() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_guardian_overview_endpoint() -> None:
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())

    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")
    res = client.get(
        "/api/v1/guardian/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["guardian_id"] == guardian_id
    assert data["tenant_id"] == tenant_id
    assert len(data["learners"]) == 1
    assert data["learners"][0]["relationship_health_trend"] == "healthy"
    assert data["consent_status"]["conversation_storage"]
    assert "session_trends" in data
    assert isinstance(data["session_trends"], list)
    assert "topic_distribution" in data
    assert isinstance(data["topic_distribution"], list)


def test_guardian_overview_session_trends_and_topics() -> None:
    """Verifies that Guardian overview populates session trends, topics, consent states, and incident timelines."""
    tenant_id = str(uuid4())
    guardian_id = str(uuid4())

    token = create_jwt_token(user_id=guardian_id, tenant_id=tenant_id, role="guardian")
    res = client.get(
        "/api/v1/guardian/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    data = res.json()

    # Session trends verify 7-day breakdown
    trends = data["session_trends"]
    assert len(trends) == 7
    assert "day" in trends[0]
    assert "minutes" in trends[0]

    # Topic distribution verify domain items
    topics = data["topic_distribution"]
    assert len(topics) >= 1
    assert "topic" in topics[0]
    assert "percentage" in topics[0]

    # Consent states verify active flags
    assert isinstance(data["consent_status"], dict)

    # Incident timeline list structure verify
    assert isinstance(data["safety_incidents"], list)


@pytest.mark.asyncio
async def test_in_memory_repository_dynamic_metrics() -> None:
    """Verifies that InMemoryDashboardRepository dynamically calculates repository metric queries."""
    from dashboard_bff.repository import InMemoryDashboardRepository
    from uuid import UUID
    repo = InMemoryDashboardRepository()
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    guardian_id = UUID("00000000-0000-0000-0000-000000000002")

    # Initial session trends check
    trends = await repo.session_trends(tenant_id, guardian_id)
    assert len(trends) == 7
    assert all("day" in t and "minutes" in t for t in trends)

    # Initial topic distribution check
    topics = await repo.topic_distribution(tenant_id)
    assert len(topics) >= 1
    assert all("topic" in t and "percentage" in t for t in topics)

    # Session count and streak check
    sc = await repo.session_count(tenant_id)
    assert sc >= 1
    streak = await repo.learner_streak(tenant_id, guardian_id)
    assert "day" in streak





def test_admin_overview_endpoint() -> None:
    tenant_id = str(uuid4())

    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="admin")
    res = client.get(
        "/api/v1/admin/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == tenant_id
    assert isinstance(data["total_learners"], int)
    assert len(data["recent_incidents"]) == 1
    assert isinstance(data["active_traces"], int)
    assert isinstance(data["safety_pass_rate"], (int, float))
    assert isinstance(data["service_latencies"], dict)
    assert isinstance(data["trace_summaries"], list)
    assert isinstance(data["system_health_logs"], list)


def test_dashboard_x_request_id_middleware() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers

    custom_id = "dashboard-req-999"
    res_custom = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res_custom.status_code == 200
    assert res_custom.headers.get("X-Request-ID") == custom_id


def test_admin_observability_metrics_endpoint() -> None:
    tenant_id = str(uuid4())
    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="admin")
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["active_traces"], int)
    assert isinstance(data["safety_triggers"], dict)
    assert isinstance(data["safety_triggers"]["safe_pass_rate"], (int, float))
    assert isinstance(data["service_latencies"], dict)
    assert isinstance(data["trace_count_hourly"], list)


def test_admin_observability_unauthenticated_returns_401() -> None:
    res = client.get("/api/v1/admin/observability/metrics")
    assert res.status_code == 401


def test_admin_observability_header_spoofing_rejected() -> None:
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"X-User-Role": "admin"},
    )
    assert res.status_code == 401


def test_admin_observability_non_admin_role_rejected() -> None:
    token = create_jwt_token(
        user_id=str(uuid4()), tenant_id=str(uuid4()), role="guardian"
    )
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_admin_observability_valid_admin_jwt_accepted() -> None:
    token = create_jwt_token(
        user_id=str(uuid4()), tenant_id=str(uuid4()), role="admin"
    )
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200


def test_learner_token_cannot_access_guardian_bff() -> None:
    token = create_jwt_token(
        user_id=str(uuid4()), tenant_id=str(uuid4()), role="learner"
    )
    res = client.get(
        "/api/v1/guardian/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403


def test_header_only_bff_request_is_unauthorized() -> None:
    res = client.get(
        "/api/v1/guardian/overview",
        headers={"X-Tenant-ID": str(uuid4()), "X-Guardian-ID": str(uuid4())},
    )
    assert res.status_code == 401
