"""
Shared configuration module for all Vadi-Pehn services.
Implements: SD §9 (config centralization), coding-standards (no os.environ outside this file).

WHAT THIS DOES: Centralized Settings dataclass loaded from environment variables.
WHAT THIS DOES NOT DO: Read os.environ directly anywhere else in the codebase.
"""
from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class MemoryDBSettings(BaseSettings):
    """PostgreSQL — Memory Service DB (learner_memories, learner_interest_profile)."""

    host: str = Field("localhost", alias="MEMORY_DB_HOST")
    port: int = Field(5432, alias="MEMORY_DB_PORT")
    name: str = Field("vadi_memory", alias="MEMORY_DB_NAME")
    user: str = Field("vadi_app", alias="MEMORY_DB_USER")
    password: str = Field("secret", alias="MEMORY_DB_PASSWORD")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    model_config = {"env_file": ".env", "extra": "ignore"}


class GovernanceDBSettings(BaseSettings):
    """PostgreSQL — Governance DB (SEPARATE INSTANCE per SD architecture non-negotiable).

    Contains: consent_records, safety_incidents, reviewer_access_log.
    Must NEVER be the same host/port/instance as MemoryDBSettings.
    """

    host: str = Field("localhost", alias="GOVERNANCE_DB_HOST")
    port: int = Field(5433, alias="GOVERNANCE_DB_PORT")
    name: str = Field("vadi_governance", alias="GOVERNANCE_DB_NAME")
    user: str = Field("vadi_gov_app", alias="GOVERNANCE_DB_USER")
    password: str = Field("secret", alias="GOVERNANCE_DB_PASSWORD")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    model_config = {"env_file": ".env", "extra": "ignore"}


class VLLMSettings(BaseSettings):
    """vLLM service URLs — accessed ONLY through safety proxy (GUARDRAILS G-001)."""

    main_url: str = Field("http://localhost:8001", alias="VLLM_MAIN_URL")
    main_model: str = Field("meta-llama/Llama-3.3-70B-Instruct", alias="VLLM_MAIN_MODEL")
    main_timeout_seconds: float = Field(30.0, alias="VLLM_MAIN_TIMEOUT_SECONDS")

    classifier_url: str = Field("http://vllm-classifier:8002", alias="VLLM_CLASSIFIER_URL")
    classifier_model: str = Field("meta-llama/Llama-Guard-3-8B", alias="VLLM_CLASSIFIER_MODEL")
    # CRITICAL: 3-second hard timeout on classifier (PRD §8, GUARDRAILS G-001)
    classifier_timeout_seconds: float = Field(3.0, alias="VLLM_CLASSIFIER_TIMEOUT_SECONDS")

    model_config = {"env_file": ".env", "extra": "ignore"}


class SafetyProxySettings(BaseSettings):
    """NeMo Guardrails safety proxy — the ONLY path to vLLM main."""

    url: str = Field("http://safety-proxy:8080", alias="SAFETY_PROXY_URL")
    # Must match VLLM_CLASSIFIER_TIMEOUT_SECONDS — fail-closed on any timeout
    timeout_seconds: float = Field(3.0, alias="SAFETY_PROXY_TIMEOUT_SECONDS")

    model_config = {"env_file": ".env", "extra": "ignore"}


class LangfuseSettings(BaseSettings):
    """Langfuse observability — PRD §12, SD §8."""

    host: str = Field("http://localhost:3000", alias="LANGFUSE_HOST")
    public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    secret_key: str = Field("", alias="LANGFUSE_SECRET_KEY")

    model_config = {"env_file": ".env", "extra": "ignore"}


class MinIOSettings(BaseSettings):
    """MinIO object storage — PRD §9 document ingestion."""

    endpoint: str = Field("localhost:9000", alias="MINIO_ENDPOINT")
    access_key: str = Field("minioadmin", alias="MINIO_ACCESS_KEY")
    secret_key: str = Field("minioadmin", alias="MINIO_SECRET_KEY")
    bucket_documents: str = Field("vadi-documents", alias="MINIO_BUCKET_DOCUMENTS")
    secure: bool = Field(False, alias="MINIO_SECURE")

    model_config = {"env_file": ".env", "extra": "ignore"}


class AuthSettings(BaseSettings):
    """JWT auth settings — PRD §13 (security hardening)."""

    jwt_secret_key: str = Field("dev_secret_key", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(30, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    model_config = {"env_file": ".env", "extra": "ignore"}


class EscalationSettings(BaseSettings):
    """On-call escalation settings — PRD §3.3 (15-minute SLA)."""

    sms_webhook_url: str = Field("", alias="ONCALL_SMS_WEBHOOK_URL")
    pager_phone: str = Field("", alias="ONCALL_PAGER_PHONE")
    # Incident SLA: 15 minutes from creation to reviewer acknowledgment (PRD §3.3)
    self_harm_sla_minutes: int = 15

    model_config = {"env_file": ".env", "extra": "ignore"}


class LiveKitSettings(BaseSettings):
    """LiveKit SFU Server Settings — PRD §6, SD §4.2."""

    url: str = Field("ws://localhost:7880", alias="LIVEKIT_URL")
    api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    api_secret: str = Field("secret", alias="LIVEKIT_API_SECRET")

    model_config = {"env_file": ".env", "extra": "ignore"}


class VoiceSettings(BaseSettings):
    """Voice Gateway Pipeline (VAD, STT, TTS, Fallbacks, Safety check-output)."""

    vad_model_path: str = Field("models/silero_vad.onnx", alias="VAD_MODEL_PATH")
    whisper_url: str = Field("http://localhost:8003", alias="WHISPER_URL")
    whisper_model: str = Field("faster-distil-whisper-large-v3", alias="WHISPER_MODEL")
    kokoro_url: str = Field("http://localhost:8004", alias="KOKORO_URL")
    piper_path: str = Field("piper", alias="PIPER_PATH")
    voice_classifier_url: str = Field("http://vllm-classifier-voice:8002", alias="VOICE_CLASSIFIER_URL")
    orchestration_url: str = Field("http://localhost:8000", alias="ORCHESTRATION_URL")

    model_config = {"env_file": ".env", "extra": "ignore"}


class PanelSettings(BaseSettings):
    """Career Panel (CrewAI + MoE + SLM OCR) Settings — PRD §5, SD §4.4."""

    max_active_relationships: int = Field(3, alias="PANEL_MAX_ACTIVE_RELATIONSHIPS")
    lapse_inactive_days: int = Field(45, alias="PANEL_LAPSE_INACTIVE_DAYS")
    ocr_confidence_threshold: float = Field(0.85, alias="SLM_OCR_CONFIDENCE_THRESHOLD")
    qwen_ocr_url: str = Field("http://localhost:8005", alias="QWEN_OCR_URL")
    moe_model_name: str = Field("vadi-moe-career-expert-v1", alias="MOE_MODEL_NAME")

    model_config = {"env_file": ".env", "extra": "ignore"}


class Settings(BaseSettings):
    """
    Root settings object. Use get_settings() in all services — never os.environ directly.
    Implements: coding-standards §3 (config centralized in Settings dataclass).
    """

    environment: str = Field("development", alias="ENVIRONMENT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    memory_db: MemoryDBSettings = MemoryDBSettings()  # type: ignore[call-arg]
    governance_db: GovernanceDBSettings = GovernanceDBSettings()  # type: ignore[call-arg]
    vllm: VLLMSettings = VLLMSettings()  # type: ignore[call-arg]
    safety_proxy: SafetyProxySettings = SafetyProxySettings()  # type: ignore[call-arg]
    langfuse: LangfuseSettings = LangfuseSettings()  # type: ignore[call-arg]
    minio: MinIOSettings = MinIOSettings()  # type: ignore[call-arg]
    auth: AuthSettings = AuthSettings()  # type: ignore[call-arg]
    escalation: EscalationSettings = EscalationSettings()  # type: ignore[call-arg]
    livekit: LiveKitSettings = LiveKitSettings()  # type: ignore[call-arg]
    voice: VoiceSettings = VoiceSettings()  # type: ignore[call-arg]
    panel: PanelSettings = PanelSettings()  # type: ignore[call-arg]

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance. Call this everywhere instead of os.environ."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
