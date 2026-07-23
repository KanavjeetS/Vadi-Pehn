"""
Empirical test harness for Milestone 5 (Admin Observability Dashboard & Telemetry Endpoints).
Verifies auth handling, schema validation, SLA metrics, 6 microservice latencies, and HTML/JS canvas element ID matching.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Ensure src directories are in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BFF_SRC = ROOT_DIR / "services" / "dashboard-bff" / "src"
API_GW_SRC = ROOT_DIR / "services" / "api-gateway" / "src"
sys.path.insert(0, str(BFF_SRC))
sys.path.insert(0, str(API_GW_SRC))
sys.path.insert(0, str(ROOT_DIR))

from dashboard_bff.main import app
from api_gateway.auth import create_jwt_token

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

REQUIRED_MICROSERVICES = {
    "API Gateway",
    "Orchestration",
    "Safety Proxy",
    "Voice Gateway",
    "Memory",
    "Governance",
}

# -----------------------------------------------------------------------------
# 1. GET /api/v1/admin/overview Tests
# -----------------------------------------------------------------------------

def test_admin_overview_valid_admin_token(client):
    tenant_id = str(uuid4())
    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="admin")

    res = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()

    # Schema checks
    assert data["tenant_id"] == tenant_id
    assert isinstance(data["total_learners"], int)
    assert isinstance(data["open_incidents_count"], int)
    assert isinstance(data["sla_breaches_count"], int)
    assert isinstance(data["discrepancy_queue_count"], int)
    assert isinstance(data["recent_incidents"], list)
    assert isinstance(data["active_traces"], int)
    assert isinstance(data["total_sessions"], int)

    # Safety pass rate check (>= 99.18%)
    assert "safety_pass_rate" in data
    assert data["safety_pass_rate"] >= 99.18

    # 6 Microservice latencies check
    latencies = data["service_latencies"]
    assert isinstance(latencies, dict)
    for service_name in REQUIRED_MICROSERVICES:
        assert service_name in latencies, f"Missing microservice: {service_name}"
        svc = latencies[service_name]
        assert "p50" in svc and isinstance(svc["p50"], (int, float))
        assert "p95" in svc and isinstance(svc["p95"], (int, float))
        assert "p99" in svc and isinstance(svc["p99"], (int, float))
        assert svc["p50"] <= svc["p95"] <= svc["p99"], f"Invalid percentile order for {service_name}"

    # Trace summaries check
    trace_summaries = data["trace_summaries"]
    assert isinstance(trace_summaries, list)
    assert len(trace_summaries) > 0
    for ts in trace_summaries:
        assert "trace_id" in ts
        assert "session_id" in ts
        assert "service" in ts
        assert "latency_ms" in ts
        assert "status" in ts
        assert "timestamp" in ts

    # System health logs check
    logs = data["system_health_logs"]
    assert isinstance(logs, list)
    assert len(logs) > 0
    for log in logs:
        assert "timestamp" in log
        assert "service" in log
        assert "level" in log
        assert "message" in log
        assert "sla_status" in log

    # SLA metrics & triggers
    assert "safety_triggers" in data
    assert "sla_metrics" in data


def test_admin_overview_missing_token(client):
    res = client.get("/api/v1/admin/overview")
    assert res.status_code in (401, 403)


def test_admin_overview_invalid_token(client):
    res = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer invalid.jwt.token.here"},
    )
    assert res.status_code in (401, 403)


def test_admin_overview_non_admin_role(client):
    tenant_id = str(uuid4())
    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="guardian")
    res = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


# -----------------------------------------------------------------------------
# 2. GET /api/v1/admin/observability/metrics Tests
# -----------------------------------------------------------------------------

def test_observability_metrics_valid_admin_token(client):
    tenant_id = str(uuid4())
    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="admin")

    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()

    # Schema checks
    assert "langfuse_host" in data
    assert data["active_traces"] == 142
    assert data["total_sessions"] == 850
    assert "voice_latency_p95_ms" in data
    assert "voice_first_chunk_p50_ms" in data

    # Safety triggers & pass rate (>= 99.18%)
    triggers = data["safety_triggers"]
    assert triggers["safe_pass_rate"] >= 99.18
    assert "unsafe_self_harm" in triggers
    assert "unsafe_general" in triggers

    # SLA metrics
    sla = data["sla_metrics"]
    assert "self_harm_15min_sla_met" in sla
    assert "average_reviewer_ack_minutes" in sla

    # 6 Microservices latencies check
    latencies = data["service_latencies"]
    for service_name in REQUIRED_MICROSERVICES:
        assert service_name in latencies, f"Missing microservice: {service_name}"
        svc = latencies[service_name]
        assert "p50" in svc and "p95" in svc and "p99" in svc
        assert svc["p50"] <= svc["p95"] <= svc["p99"]

    # Hourly trace count & summaries & logs
    assert len(data["trace_count_hourly"]) > 0
    assert len(data["trace_summaries"]) > 0
    assert len(data["system_health_logs"]) > 0


def test_observability_metrics_missing_token(client):
    res = client.get("/api/v1/admin/observability/metrics")
    assert res.status_code == 403


def test_observability_metrics_invalid_token(client):
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert res.status_code == 403


def test_observability_metrics_x_user_role_fallback(client):
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"X-User-Role": "admin"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["active_traces"] == 142


def test_observability_metrics_non_admin_role(client):
    tenant_id = str(uuid4())
    token = create_jwt_token(user_id=str(uuid4()), tenant_id=tenant_id, role="learner")
    res = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


# -----------------------------------------------------------------------------
# 3. Canvas Element ID Verification (HTML vs JS)
# -----------------------------------------------------------------------------

def test_canvas_element_ids_matching():
    html_path = ROOT_DIR / "webapp" / "admin" / "index.html"
    js_path = ROOT_DIR / "webapp" / "admin" / "admin.js"

    assert html_path.exists(), "index.html does not exist"
    assert js_path.exists(), "admin.js does not exist"

    html_content = html_path.read_text(encoding="utf-8")
    js_content = js_path.read_text(encoding="utf-8")

    # Extract canvas IDs from HTML (<canvas ... id="xyz" ...)
    html_canvas_ids = set(re.findall(r'<canvas[^>]*id=["\']([^"\']+)["\']', html_content))

    # Extract canvas IDs referenced in JS (document.getElementById('xyz'))
    js_canvas_ids = set(re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)", js_content))
    # Filter to only IDs used for chart canvas rendering
    js_chart_canvas_ids = {id_name for id_name in js_canvas_ids if "Chart" in id_name}

    assert len(html_canvas_ids) > 0, "No canvas elements found in index.html"
    assert len(js_chart_canvas_ids) > 0, "No chart canvas IDs found in admin.js"

    # Verify 100% match between HTML canvas IDs and JS chart canvas IDs
    missing_in_js = html_canvas_ids - js_chart_canvas_ids
    missing_in_html = js_chart_canvas_ids - html_canvas_ids

    assert not missing_in_js, f"Canvas IDs in HTML but not targeted in JS: {missing_in_js}"
    assert not missing_in_html, f"Canvas IDs in JS but missing in HTML: {missing_in_html}"
    assert html_canvas_ids == js_chart_canvas_ids, "Canvas IDs do not match 100%"

    # Explicitly check expected canvas IDs
    expected_ids = {"traceVolumeChart", "safetyPassRateChart", "microserviceLatencyChart"}
    assert html_canvas_ids == expected_ids, f"Expected {expected_ids}, got {html_canvas_ids}"
