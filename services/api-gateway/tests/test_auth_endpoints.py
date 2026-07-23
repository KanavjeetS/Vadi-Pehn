"""
Unit & Integration Tests for Multi-Role Auth Endpoints.
Implements: Requirement R2 (Multi-Role Authentication, Login & Signup System with Demo Toggles).
Verifies:
  1. POST /api/v1/auth/login for 'learner', 'guardian', 'admin' roles.
  2. POST /api/v1/auth/demo for 'learner', 'guardian', 'admin' roles with fixed demo UUIDs.
  3. Role validation failure (422 Unprocessable Entity).
  4. Missing credentials validation failure (422 Unprocessable Entity).
  5. Cryptographic signature and token scope decoding.
  6. CORS preflight OPTIONS request support on auth endpoints.
"""

from __future__ import annotations

import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from api_gateway.auth import decode_jwt_token
from api_gateway.main import app

client = TestClient(app)

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEMO_GUARDIAN_ID = "00000000-0000-0000-0000-000000000002"
DEMO_LEARNER_ID = "00000000-0000-0000-0000-000000000003"
DEMO_ADMIN_ID = "00000000-0000-0000-0000-000000000004"


def test_auth_demo_learner():
    response = client.post("/api/v1/auth/demo", json={"role": "learner"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "learner"
    assert data["tenant_id"] == DEMO_TENANT_ID
    assert data["user_id"] == DEMO_LEARNER_ID
    assert data["token_type"] == "Bearer"
    assert "access_token" in data and len(data["access_token"]) > 0

    # Cryptographic JWT verification
    payload = decode_jwt_token(data["access_token"])
    assert payload["role"] == "learner"
    assert payload["sub"] == DEMO_LEARNER_ID
    assert payload["tenant_id"] == DEMO_TENANT_ID


def test_auth_demo_guardian():
    response = client.post("/api/v1/auth/demo", json={"role": "guardian"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "guardian"
    assert data["tenant_id"] == DEMO_TENANT_ID
    assert data["user_id"] == DEMO_GUARDIAN_ID

    payload = decode_jwt_token(data["access_token"])
    assert payload["role"] == "guardian"
    assert payload["sub"] == DEMO_GUARDIAN_ID


def test_auth_demo_admin():
    response = client.post("/api/v1/auth/demo", json={"role": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    assert data["tenant_id"] == DEMO_TENANT_ID
    assert data["user_id"] == DEMO_ADMIN_ID

    payload = decode_jwt_token(data["access_token"])
    assert payload["role"] == "admin"
    assert payload["sub"] == DEMO_ADMIN_ID


def test_auth_demo_invalid_role():
    response = client.post("/api/v1/auth/demo", json={"role": "super_user"})
    assert response.status_code == 422
    assert "Invalid role" in response.json()["detail"]


def test_auth_login_learner():
    payload = {
        "email": "child@vadi.demo",
        "password": "demoPassword123",
        "role": "learner",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "learner"
    assert data["tenant_id"] == DEMO_TENANT_ID
    assert data["user_id"] == DEMO_LEARNER_ID
    assert "access_token" in data

    token_claims = decode_jwt_token(data["access_token"])
    assert token_claims["role"] == "learner"
    assert token_claims["sub"] == DEMO_LEARNER_ID


def test_auth_login_guardian():
    payload = {
        "email": "guardian@vadi.demo",
        "password": "demoPassword123",
        "role": "guardian",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "guardian"
    assert data["tenant_id"] == DEMO_TENANT_ID
    assert data["user_id"] == DEMO_GUARDIAN_ID
    assert "access_token" in data

    token_claims = decode_jwt_token(data["access_token"])
    assert token_claims["role"] == "guardian"


def test_auth_login_admin():
    payload = {
        "email": "admin@vadi.demo",
        "password": "demoPassword123",
        "role": "admin",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    assert data["tenant_id"] == DEMO_TENANT_ID
    assert data["user_id"] == DEMO_ADMIN_ID
    assert "access_token" in data

    token_claims = decode_jwt_token(data["access_token"])
    assert token_claims["role"] == "admin"


def test_auth_login_invalid_role():
    payload = {
        "email": "user@vadi.demo",
        "password": "password123",
        "role": "invalid_role",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422
    assert "Invalid role" in response.json()["detail"]


def test_auth_login_missing_credentials():
    payload = {
        "email": "",
        "password": "",
        "role": "learner",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422


def test_auth_signup_learner():
    payload = {
        "email": "newuser@vadi.demo",
        "password": "securePassword123",
        "display_name": "New Learner",
        "role": "learner",
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "learner"
    assert data["token_type"] == "Bearer"
    assert "access_token" in data and len(data["access_token"]) > 0

    token_claims = decode_jwt_token(data["access_token"])
    assert token_claims["role"] == "learner"
    assert token_claims["sub"] == data["user_id"]
    assert token_claims["tenant_id"] == data["tenant_id"]


def test_auth_cors_options_preflight():
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response_login = client.options("/api/v1/auth/login", headers=headers)
    assert response_login.status_code == 200

    response_demo = client.options("/api/v1/auth/demo", headers=headers)
    assert response_demo.status_code == 200

    response_signup = client.options("/api/v1/auth/signup", headers=headers)
    assert response_signup.status_code == 200
