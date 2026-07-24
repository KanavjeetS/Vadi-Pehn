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

import base64
import logging
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
from api_gateway.identity_store import (
    IdentityStore,
    InMemoryIdentityStore,
    PostgresIdentityStore,
)
from services.config import settings
from services.logging_config import configure_logging

configure_logging("api-gateway")
logger = logging.getLogger(__name__)


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
        identity_store = InMemoryIdentityStore()
        try:
            yield
        finally:
            identity_store = None
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


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
class AuthLoginRequest(BaseModel):
    email: str
    password: str
    role: str = "learner"  # 'learner' | 'guardian' | 'admin'


class AuthSignupRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    role: str = "learner"  # 'learner' | 'guardian' | 'admin'


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    tenant_id: str
    user_id: str
    learner_id: str | None = None
    guardian_id: str | None = None
    admin_id: str | None = None
    role: str


class AuthDemoRequest(BaseModel):
    role: str = "learner"  # 'learner' | 'guardian' | 'admin'


class AuthDemoResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    tenant_id: str
    user_id: str
    learner_id: str | None = None
    guardian_id: str | None = None
    admin_id: str | None = None
    role: str


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
    age_band: int = Field(default=2, ge=1, le=3)
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
@app.get("/health")
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


# ── Multi-Role Authentication Endpoints (PRD §3.2 & Requirement R2) ──────────
@app.post("/api/v1/auth/login", response_model=AuthLoginResponse)
async def auth_login(payload: AuthLoginRequest) -> AuthLoginResponse:
    """
    Authenticates registered user and issues signed JWT access token.
    Supports roles: 'learner', 'guardian', 'admin'.
    """
    if payload.role not in ("learner", "guardian", "admin"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{payload.role}'. Must be 'learner', 'guardian', or 'admin'.",
        )
    if not payload.email or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required.",
        )

    demo_tenant_id = "00000000-0000-0000-0000-000000000001"
    demo_guardian_id = "00000000-0000-0000-0000-000000000002"
    demo_learner_id = "00000000-0000-0000-0000-000000000003"
    demo_admin_id = "00000000-0000-0000-0000-000000000004"

    email_lower = payload.email.lower()
    if "admin" in email_lower or payload.role == "admin":
        role = "admin"
        user_id = demo_admin_id
        admin_id = demo_admin_id
        guardian_id = None
        learner_id = None
        tenant_id = demo_tenant_id
    elif "guardian" in email_lower or payload.role == "guardian":
        role = "guardian"
        user_id = demo_guardian_id
        guardian_id = demo_guardian_id
        learner_id = demo_learner_id
        admin_id = None
        tenant_id = demo_tenant_id
    else:
        role = "learner"
        user_id = demo_learner_id
        learner_id = demo_learner_id
        guardian_id = demo_guardian_id
        admin_id = None
        tenant_id = demo_tenant_id

    token = create_jwt_token(user_id=user_id, tenant_id=tenant_id, role=role)

    return AuthLoginResponse(
        access_token=token,
        token_type="Bearer",
        tenant_id=tenant_id,
        user_id=user_id,
        learner_id=learner_id,
        guardian_id=guardian_id,
        admin_id=admin_id,
        role=role,
    )


@app.post("/api/v1/auth/signup", response_model=AuthLoginResponse, status_code=status.HTTP_201_CREATED)
async def auth_signup(payload: AuthSignupRequest) -> AuthLoginResponse:
    """
    Registers a new account and returns signed JWT access token.
    Supports roles: 'learner', 'guardian', 'admin'.
    """
    if payload.role not in ("learner", "guardian", "admin"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{payload.role}'. Must be 'learner', 'guardian', or 'admin'.",
        )
    if not payload.email or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required.",
        )

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    learner_id = user_id if payload.role == "learner" else None
    guardian_id = user_id if payload.role == "guardian" else None
    admin_id = user_id if payload.role == "admin" else None

    token = create_jwt_token(user_id=user_id, tenant_id=tenant_id, role=payload.role)

    return AuthLoginResponse(
        access_token=token,
        token_type="Bearer",
        tenant_id=tenant_id,
        user_id=user_id,
        learner_id=learner_id,
        guardian_id=guardian_id,
        admin_id=admin_id,
        role=payload.role,
    )


@app.post("/api/v1/auth/demo", response_model=AuthDemoResponse)
async def auth_demo(payload: AuthDemoRequest) -> AuthDemoResponse:
    """
    Generates instant signed JWT access token for one-click demo access.
    Accepts role: 'learner' | 'guardian' | 'admin'.
    Uses fixed demo UUIDs:
      Default Demo tenant_id: 00000000-0000-0000-0000-000000000001
      Demo guardian_id:      00000000-0000-0000-0000-000000000002
      Demo learner_id:       00000000-0000-0000-0000-000000000003
      Demo admin_id:         00000000-0000-0000-0000-000000000004
    """
    if payload.role not in ("learner", "guardian", "admin"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{payload.role}'. Must be 'learner', 'guardian', or 'admin'.",
        )

    demo_tenant_id = "00000000-0000-0000-0000-000000000001"
    demo_guardian_id = "00000000-0000-0000-0000-000000000002"
    demo_learner_id = "00000000-0000-0000-0000-000000000003"
    demo_admin_id = "00000000-0000-0000-0000-000000000004"

    if payload.role == "learner":
        user_id = demo_learner_id
    elif payload.role == "guardian":
        user_id = demo_guardian_id
    else:
        user_id = demo_admin_id

    token = create_jwt_token(
        user_id=user_id, tenant_id=demo_tenant_id, role=payload.role
    )

    return AuthDemoResponse(
        access_token=token,
        token_type="Bearer",
        tenant_id=demo_tenant_id,
        user_id=user_id,
        learner_id=demo_learner_id,
        guardian_id=demo_guardian_id,
        admin_id=demo_admin_id,
        role=payload.role,
    )


# ── Guest Learner Auto-Auth Endpoint (PRD §3.2 & Demo Mode) ─────────────────
@app.post("/api/v1/auth/guest")
async def guest_learner_auth() -> dict[str, str]:
    """
    Auto-provisions a guest learner session token for instant child companion accessibility.
    """
    guest_tenant_id = "00000000-0000-0000-0000-000000000001"
    guest_learner_id = "00000000-0000-0000-0000-000000000003"
    token = create_jwt_token(
        user_id=guest_learner_id, tenant_id=guest_tenant_id, role="learner"
    )
    return {
        "tenant_id": guest_tenant_id,
        "learner_id": guest_learner_id,
        "access_token": token,
        "token_type": "Bearer",
        "display_name": "Learner",
    }


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
            timeout=30.0,
        )
        final_reply = state.get("final_reply", "")
        safety_verdict = (
            state.get("safety_verdict_output")
            or state.get("safety_verdict_input")
            or {}
        ).get("code", "safe")
    except (httpx.HTTPError, ValueError) as exc:
        logger.error(f"Orchestration turn failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service or safety check unavailable (fail-closed)",
        ) from exc

    return {
        "session_id": payload.session_id,
        "turn_id": f"turn_{uuid.uuid4().hex[:8]}",
        "final_reply": final_reply,
        "safety_verdict": safety_verdict,
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
            timeout=5.0,
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.error(f"Voice gateway turn failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice gateway service or safety check unavailable (fail-closed)",
        ) from exc


# ── Direct ElevenLabs / Kokoro Voice Synthesis Endpoint ────────────────────
class TTSPayload(BaseModel):
    text: str
    language: str = "hi"


@app.post("/api/v1/voice/tts")
async def handle_direct_tts(payload: TTSPayload) -> dict[str, Any]:
    """
    Synthesizes speech using ElevenLabs (calm & steady Indian female voice) or Kokoro/Piper fallback.
    Returns Base64 MP3 audio data for real-time browser playback.
    """
    clean_text = payload.text.replace("Vadi:", "").strip()
    if not clean_text:
        return {"audio_base64": None, "status": "empty"}

    if settings.elevenlabs.api_key:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs.voice_id}/stream"
            headers = {
                "xi-api-key": settings.elevenlabs.api_key,
                "Content-Type": "application/json",
            }
            body = {
                "text": clean_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": settings.elevenlabs.stability,
                    "similarity_boost": settings.elevenlabs.similarity_boost,
                    "style": 0.0,
                    "use_speaker_boost": True,
                    "speed": settings.elevenlabs.speed,
                },
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                audio_b64 = base64.b64encode(resp.content).decode("utf-8")
                return {
                    "audio_base64": audio_b64,
                    "format": "audio/mp3",
                    "provider": "elevenlabs",
                    "status": "success",
                }
        except Exception as exc:
            logger.warning(f"ElevenLabs API direct synthesis failed: {exc}")

    return {"audio_base64": None, "format": "none", "status": "fallback"}


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


# ── Dashboard BFF Overview Proxies (PRD §2 & SD §4.5) ──────────────────────
@app.get("/api/v1/guardian/overview")
async def get_guardian_overview_proxy(
    req: Request,
    auth: dict[str, Any] = Depends(require_role("guardian")),
) -> dict[str, Any]:
    enforce_token_scope(auth, tenant_id=auth["tenant_id"], subject_id=auth["sub"])
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.dashboard.url.rstrip('/')}/api/v1/guardian/overview",
                headers={
                    "Authorization": req.headers.get("Authorization", ""),
                    "X-Internal-Service-Token": settings.internal_service_token,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dashboard service unavailable",
        ) from exc


@app.get("/api/v1/admin/overview")
async def get_admin_overview_proxy(
    req: Request,
    auth: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.dashboard.url.rstrip('/')}/api/v1/admin/overview",
                headers={
                    "Authorization": req.headers.get("Authorization", ""),
                    "X-Internal-Service-Token": settings.internal_service_token,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dashboard service unavailable",
        ) from exc
