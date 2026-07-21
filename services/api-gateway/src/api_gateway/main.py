"""
API Gateway — Unified Entry Point for Vadi-Pehn Platform.
Implements: PRD §3.2 (Guardian Enrollment & Learner Provisioning),
           PRD §5.4 (Internal & External API Contracts),
           PRD §13 (Security Hardening: signed role-scoped JWTs, rate-limiting).

Routes:
  POST /api/v1/guardian/enroll   → Guardian Verification & Account Creation
  POST /api/v1/guardian/learners → Provision Linked Minor Account (Requires Guardian Auth)
  POST /api/v1/turn              → Orchestration Service Text Turn (Requires Learner Auth)
  POST /api/v1/voice/turn        → Voice Gateway Voice Turn (Requires Learner Auth)
  POST /api/v1/guardian/consent  → Governance Service Consent Update (Requires Guardian Auth)
  POST /api/v1/documents/upload  → Ingestion Service Document Upload (Requires Guardian/Learner Auth)
  GET  /healthz                  → Health Check
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api_gateway.auth import (
    create_jwt_token,
    enforce_token_scope,
    require_role,
    verify_auth_token,
)
from api_gateway.identity_store import IdentityStore, PostgresIdentityStore
from services.config import settings


async def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        timeout=timeout or settings.vllm.main_timeout_seconds
    ) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


identity_store: IdentityStore | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global identity_store
    if settings.is_dev:
        yield
        return
    pool = await asyncpg.create_pool(settings.memory_db.dsn, min_size=1, max_size=5)
    identity_store = PostgresIdentityStore(pool)
    try:
        yield
    finally:
        identity_store = None
        await pool.close()


app = FastAPI(title="Vadi-Pehn API Gateway", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate-limiting store
RATE_LIMIT_STORE: dict[str, list[float]] = {}
MAX_REQUESTS_PER_MINUTE = 60


def check_rate_limit(client_id: str) -> None:
    now = time.time()
    timestamps = RATE_LIMIT_STORE.get(client_id, [])
    valid_timestamps = [t for t in timestamps if now - t < 60.0]
    if len(valid_timestamps) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before making more requests.",
        )
    valid_timestamps.append(now)
    RATE_LIMIT_STORE[client_id] = valid_timestamps


# Request/Response Models
class GuardianEnrollmentRequest(BaseModel):
    tenant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    guardian_name: str
    phone_number: str
    verification_method: str = (
        "ngo_cosign"  # 'ngo_cosign' | 'guardian_otp' | 'in_person'
    )
    caseworker_id: str | None = None


class GuardianEnrollmentResponse(BaseModel):
    guardian_id: str
    tenant_id: str
    verification_status: str
    access_token: str
    token_type: str = "Bearer"


class LearnerProvisionRequest(BaseModel):
    display_name: str
    age_band: int = Field(ge=1, le=3)
    preferred_language: str = "hi"


class LearnerProvisionResponse(BaseModel):
    learner_id: str
    tenant_id: str
    guardian_id: str
    display_name: str
    access_token: str
    token_type: str = "Bearer"


class TextTurnPayload(BaseModel):
    session_id: str
    tenant_id: str
    learner_id: str
    age_band: int = Field(ge=1, le=3)
    message_text: str
    language: str = "hi"


class VoiceTurnPayload(BaseModel):
    session_id: str
    tenant_id: str
    learner_id: str
    age_band: int
    audio_data_base64: str | None = None
    text_fallback: str | None = None
    language: str = "hi"


class ConsentPayload(BaseModel):
    tenant_id: str
    learner_id: str
    guardian_id: str
    consent_type: str
    granted: bool
    verification_method: str = "ngo_cosign"


class DocumentUploadPayload(BaseModel):
    tenant_id: str
    learner_id: str
    file_name: str
    file_bytes_base64: str
    in_app_expected_grade: str | None = None


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


# ── Guardian Enrollment Flow (PRD §3.2) ────────────────────────────────────
@app.post(
    "/api/v1/guardian/enroll",
    response_model=GuardianEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_guardian(
    payload: GuardianEnrollmentRequest,
) -> GuardianEnrollmentResponse:
    """
    Verifies guardian identity via NGO co-signature, OTP, or in-person verification.
    Issues short-lived signed JWT with role='guardian'.
    """
    if identity_store is None:
        raise HTTPException(status_code=503, detail="identity persistence is not ready")
    if payload.verification_method == "ngo_cosign" and not payload.caseworker_id:
        raise HTTPException(status_code=422, detail="NGO co-signature is required")
    tenant_uuid = UUID(payload.tenant_id)
    created = await identity_store.create_guardian(
        tenant_id=tenant_uuid,
        guardian_name=payload.guardian_name,
        phone_number=payload.phone_number,
        verification_method=payload.verification_method,
        verified=bool(payload.caseworker_id),
    )
    guardian_id = created["guardian_id"]
    if created["verification_status"] != "verified":
        return GuardianEnrollmentResponse(
            guardian_id=guardian_id,
            tenant_id=payload.tenant_id,
            verification_status="pending",
            access_token="",
        )
    token = create_jwt_token(
        user_id=guardian_id, tenant_id=payload.tenant_id, role="guardian"
    )

    return GuardianEnrollmentResponse(
        guardian_id=guardian_id,
        tenant_id=payload.tenant_id,
        verification_status="verified",
        access_token=token,
    )


# ── Minor Learner Provisioning Flow (PRD §3.2) ──────────────────────────────
@app.post(
    "/api/v1/guardian/learners",
    response_model=LearnerProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_learner(
    payload: LearnerProvisionRequest,
    auth: dict[str, Any] = Depends(require_role("guardian")),
) -> LearnerProvisionResponse:
    """
    Guardian provisions a linked minor learner account.
    NO child can self-signup (PRD §3.2). Issues short-lived signed JWT with role='learner'.
    """
    if identity_store is None:
        raise HTTPException(status_code=503, detail="identity persistence is not ready")
    guardian_id = UUID(auth["sub"])
    tenant_id = UUID(auth["tenant_id"])
    learner = await identity_store.create_learner(
        tenant_id=tenant_id,
        guardian_id=guardian_id,
        display_name=payload.display_name,
        age_band=payload.age_band,
        preferred_language=payload.preferred_language,
    )
    learner_id = learner["learner_id"]

    token = create_jwt_token(
        user_id=learner_id, tenant_id=str(tenant_id), role="learner"
    )

    return LearnerProvisionResponse(
        learner_id=learner_id,
        tenant_id=str(tenant_id),
        guardian_id=str(guardian_id),
        display_name=payload.display_name,
        access_token=token,
    )


# ── Child Text Turn Endpoint (Requires role='learner') ──────────────────────
@app.post("/api/v1/turn")
async def handle_text_turn(
    payload: TextTurnPayload,
    req: Request,
    auth: dict[str, Any] = Depends(require_role("learner")),
) -> dict[str, Any]:
    enforce_token_scope(
        auth, tenant_id=payload.tenant_id, subject_id=payload.learner_id
    )
    client_ip = req.client.host if req.client else "unknown"
    check_rate_limit(f"{client_ip}:{payload.learner_id}")

    try:
        state = await _post_json(
            f"{settings.voice.orchestration_url.rstrip('/')}/internal/v1/orchestration/turn",
            {
                "session_id": payload.session_id,
                "tenant_id": payload.tenant_id,
                "learner_id": payload.learner_id,
                "age_band": payload.age_band,
                "message_text": payload.message_text,
                "language": payload.language,
            },
            headers=(
                {"X-Internal-Service-Token": settings.internal_service_token}
                if settings.internal_service_token
                else {}
            ),
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="orchestration service unavailable"
        ) from exc

    return {
        "session_id": payload.session_id,
        "turn_id": state.get("turn_id"),
        "final_reply": state.get("final_reply", ""),
        "safety_verdict": (
            state.get("safety_verdict_output")
            or state.get("safety_verdict_input")
            or {}
        ).get("code"),
        "status": "success",
    }


# ── Child Voice Turn Endpoint (Requires role='learner') ─────────────────────
@app.post("/api/v1/voice/turn")
async def handle_voice_turn(
    payload: VoiceTurnPayload,
    req: Request,
    auth: dict[str, Any] = Depends(require_role("learner")),
) -> dict[str, Any]:
    enforce_token_scope(
        auth, tenant_id=payload.tenant_id, subject_id=payload.learner_id
    )
    client_ip = req.client.host if req.client else "unknown"
    check_rate_limit(f"{client_ip}:{payload.learner_id}")

    try:
        return await _post_json(
            f"{settings.voice.gateway_url.rstrip('/')}/internal/v1/voice/turn",
            payload.model_dump(mode="json"),
            headers=(
                {"X-Internal-Service-Token": settings.internal_service_token}
                if settings.internal_service_token
                else {}
            ),
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="voice gateway unavailable"
        ) from exc


# ── Guardian Consent Management (Requires role='guardian') ────────────────
@app.post("/api/v1/guardian/consent")
async def update_consent(
    payload: ConsentPayload,
    auth: dict[str, Any] = Depends(require_role("guardian")),
) -> dict[str, Any]:
    enforce_token_scope(
        auth, tenant_id=payload.tenant_id, subject_id=payload.guardian_id
    )
    consent_field = {
        "conversation_storage": "conversation_storage",
        "document_ingestion": "document_ingestion",
        "voice_recording": "voice_recording",
        "career_introductions": "career_introductions",
    }.get(payload.consent_type)
    if consent_field is None:
        raise HTTPException(status_code=422, detail="Unsupported consent type")
    try:
        record = await _post_json(
            f"{settings.governance.url.rstrip('/')}/internal/v1/governance/consent/{payload.learner_id}",
            {consent_field: payload.granted},
            headers={
                "X-Tenant-ID": payload.tenant_id,
                "X-Guardian-ID": payload.guardian_id,
                "X-Internal-Service-Token": settings.internal_service_token,
            },
            timeout=3.0,
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="governance service unavailable"
        ) from exc
    return {
        "status": "updated",
        "learner_id": payload.learner_id,
        "consent_type": payload.consent_type,
        "granted": payload.granted,
        "consent": record,
    }


# ── Document Upload (Requires Auth) ───────────────────────────────────────
@app.post("/api/v1/documents/upload")
async def upload_document(
    payload: DocumentUploadPayload,
    auth: dict[str, Any] = Depends(verify_auth_token),
) -> dict[str, Any]:
    enforce_token_scope(auth, tenant_id=payload.tenant_id)
    if auth.get("role") == "learner":
        enforce_token_scope(
            auth, tenant_id=payload.tenant_id, subject_id=payload.learner_id
        )
    try:
        return await _post_json(
            f"{settings.ingestion.url.rstrip('/')}/internal/v1/documents/upload",
            payload.model_dump(),
            headers={
                "X-Internal-Service-Token": settings.internal_service_token,
            },
            timeout=30.0,
        )
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document ingestion service unavailable",
        ) from exc
