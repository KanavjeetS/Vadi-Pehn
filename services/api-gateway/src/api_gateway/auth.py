"""
Cryptographic Role-Based Authentication Module for Vadi-Pehn.
Implements: PRD §3.2 (Guardian Verification & Learner Account Model),
           PRD §13 (Security Hardening: short-lived role-scoped JWTs).

Enforces:
  1. Role claims: 'guardian' vs 'learner'.
  2. Server-side HMAC-SHA256 signature & expiration verification.
  3. Strict role-isolation: learner tokens CANNOT access guardian routes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, Header, status

from services.config import settings

TOKEN_EXPIRATION_SECONDS = settings.auth.access_token_expire_minutes * 60


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64_decode(data_str: str) -> bytes:
    padding = "=" * (4 - (len(data_str) % 4)) if len(data_str) % 4 != 0 else ""
    return base64.urlsafe_b64decode((data_str + padding).encode("utf-8"))


def create_jwt_token(*, user_id: str, tenant_id: str, role: str) -> str:
    """
    Creates an HMAC-SHA256 signed JWT token with explicit role claim using standard library.
    """
    if role not in ("guardian", "learner", "admin"):
        raise ValueError(f"Invalid auth role '{role}'")

    now = int(time.time())
    header = {"alg": settings.auth.jwt_algorithm, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + TOKEN_EXPIRATION_SECONDS,
    }

    header_b64 = _b64_encode(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(payload).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(
        settings.auth.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    sig_b64 = _b64_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_jwt_token(token: str) -> dict[str, Any]:
    """
    Decodes and cryptographically verifies token signature and expiration.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token structure",
            )

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

        if header_b64 == "" or payload_b64 == "" or sig_b64 == "":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token"
            )

        header = json.loads(_b64_decode(header_b64).decode("utf-8"))
        if (
            header.get("alg") != settings.auth.jwt_algorithm
            or header.get("typ") != "JWT"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unsupported token algorithm",
            )

        expected_sig = hmac.new(
            settings.auth.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        provided_sig = _b64_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
            )

        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        now = int(time.time())
        if not isinstance(payload.get("sub"), str) or not isinstance(
            payload.get("tenant_id"), str
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token scope"
            )
        if payload.get("role") not in ("guardian", "learner", "admin"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token role"
            )
        if payload.get("exp", 0) <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )

        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
        )


def verify_auth_token(authorization: str | None = Header(None)) -> dict[str, Any]:
    """
    FastAPI dependency to extract and verify Bearer token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.split("Bearer ")[1].strip()
    return decode_jwt_token(token)


def require_role(required_role: str):
    """
    FastAPI dependency factory enforcing server-side role claims.
    """

    def role_checker(
        token_payload: dict[str, Any] = Depends(verify_auth_token),
    ) -> dict[str, Any]:
        user_role = token_payload.get("role")
        if user_role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires role '{required_role}', but token has role '{user_role}'.",
            )
        return token_payload

    return role_checker


def enforce_token_scope(
    token_payload: dict[str, Any], *, tenant_id: str, subject_id: str | None = None
) -> None:
    """Bind request scope to signed claims; request-body IDs cannot override auth."""
    if token_payload.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant scope does not match token",
        )
    if subject_id is not None and token_payload.get("sub") != subject_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subject scope does not match token",
        )
