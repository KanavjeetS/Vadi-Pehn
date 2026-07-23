"""
Shared configuration module for all Vadi-Pehn services.
Implements: SD §9 (config centralization), coding-standards (no os.environ outside this file).

WHAT THIS DOES: Centralized Settings dataclass loaded from environment variables.
WHAT THIS DOES NOT DO: Read os.environ directly anywhere else in the codebase.
"""

from __future__ import annotations

from functools import lru_cache
import hmac
from fastapi import HTTPException, status
from pydantic import Field
from pydantic_settings import BaseSettings


class MemoryDBSettings(BaseSettings):
    """PostgreSQL — Memory Service DB (learner_memories, learner_interest_profile)."""

    host: str = Field("localhost", alias="MEMORY_DB_HOST")
    port: int = Field(5432, alias="MEMORY_DB_PORT")
    name: str = Field("vadi_memory", alias="MEMORY_DB_NAME")
    user: str = Field("vadi_app", alias="MEMORY_DB_USER")
    password: str = Field("secret", alias="MEMORY_DB_PASSWORD")
    dsn_override: str | None = Field(None, alias="MEMORY_DB_DSN")
    embedding_url: str = Field("http://ollama:11434", alias="MEMORY_EMBEDDING_URL")
    embedding_model: str = Field("nomic-embed-text", alias="MEMORY_EMBEDDING_MODEL")

    @property
    def dsn(self) -> str:
        if self.dsn_override and self.dsn_override.strip():
            return self.dsn_override.strip()
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
    dsn_override: str | None = Field(None, alias="GOVERNANCE_DB_DSN")

    @property
    def dsn(self) -> str:
        if self.dsn_override and self.dsn_override.strip():
            return self.dsn_override.strip()
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    model_config = {"env_file": ".env", "extra": "ignore"}


class MongoDBSettings(BaseSettings):
    """MongoDB Atlas — NoSQL Document & Telemetry Logging Store."""

    uri: str = Field("mongodb://localhost:27017", alias="MONGODB_URI")
    username: str = Field("vadi_nosql_app", alias="MONGODB_USERNAME")
    password: str = Field("change_me_mongodb_password", alias="MONGODB_PASSWORD")
    db_name: str = Field("vadi_nosql", alias="MONGODB_DB_NAME")

    model_config = {"env_file": ".env", "extra": "ignore"}


class SupabaseSettings(BaseSettings):
    """Supabase API details and connection configuration."""

    url: str = Field("https://nmpyggtpigzoxjwcsfvz.supabase.co", alias="NEXT_PUBLIC_SUPABASE_URL")
    publishable_key: str = Field("change_me_supabase_pub_key", alias="NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    secret_key: str = Field("change_me_supabase_secret_key", alias="SUPABASE_SECRET_KEY")

    model_config = {"env_file": ".env", "extra": "ignore"}


class VLLMSettings(BaseSettings):
    """vLLM service URLs — accessed ONLY through safety proxy (GUARDRAILS G-001)."""

    main_url: str = Field("http://localhost:8001", alias="VLLM_MAIN_URL")
    main_model: str = Field(
        "meta-llama/Llama-3.3-70B-Instruct", alias="VLLM_MAIN_MODEL"
    )
    main_timeout_seconds: float = Field(30.0, alias="VLLM_MAIN_TIMEOUT_SECONDS")

    classifier_url: str = Field(
        "http://vllm-classifier:8002", alias="VLLM_CLASSIFIER_URL"
    )
    classifier_model: str = Field(
        "meta-llama/Llama-Guard-3-8B", alias="VLLM_CLASSIFIER_MODEL"
    )
    # CRITICAL: 3-second hard timeout on classifier (PRD §8, GUARDRAILS G-001)
    classifier_timeout_seconds: float = Field(
        3.0, alias="VLLM_CLASSIFIER_TIMEOUT_SECONDS"
    )
    nvidia_api_key: str = Field("", alias="NVIDIA_API_KEY")

    model_config = {"env_file": ".env", "extra": "ignore"}


class SafetyProxySettings(BaseSettings):
    """NeMo Guardrails safety proxy — the ONLY path to vLLM main."""

    url: str = Field("http://safety-proxy:8080", alias="SAFETY_PROXY_URL")
    # Must match VLLM_CLASSIFIER_TIMEOUT_SECONDS — fail-closed on any timeout
    timeout_seconds: float = Field(3.0, alias="SAFETY_PROXY_TIMEOUT_SECONDS")
    # Explicitly opt-in for isolated tests only; production/dev runtime stays fail-closed.
    allow_dev_bypass: bool = Field(False, alias="SAFETY_PROXY_ALLOW_DEV_BYPASS")

    model_config = {"env_file": ".env", "extra": "ignore"}


class GovernanceServiceSettings(BaseSettings):
    """Governance Service endpoint and redundant on-call paging webhook."""

    url: str = Field("http://governance-service:8000", alias="GOVERNANCE_SERVICE_URL")
    sms_webhook_url: str = Field("", alias="ONCALL_SMS_WEBHOOK_URL")

    model_config = {"env_file": ".env", "extra": "ignore"}


class IngestionServiceSettings(BaseSettings):
    """Document ingestion service boundary."""

    url: str = Field("http://ingestion-service:8000", alias="INGESTION_SERVICE_URL")

    model_config = {"env_file": ".env", "extra": "ignore"}


class DashboardBFFSettings(BaseSettings):
    """Dashboard BFF service boundary."""

    url: str = Field("http://dashboard-bff:8000", alias="DASHBOARD_BFF_URL")

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
    access_token_expire_minutes: int = Field(
        60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
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


class GroqSettings(BaseSettings):
    """Ultra-low latency Groq Cloud Inference API — Sub-100ms LLM & STT."""

    api_key: str = Field("", alias="GROQ_API_KEY")
    stt_model: str = Field("whisper-large-v3", alias="GROQ_STT_MODEL")
    llm_model: str = Field("llama-3.3-70b-versatile", alias="GROQ_LLM_MODEL")

    model_config = {"env_file": ".env", "extra": "ignore"}


class ElevenLabsSettings(BaseSettings):
    """ElevenLabs Ultra-realistic low-latency streaming TTS API."""

    api_key: str = Field("", alias="ELEVENLABS_API_KEY")
    voice_id: str = Field("2EiwWnXFnvU5JabPnv8n", alias="ELEVENLABS_VOICE_ID")  # Indian female calm voice
    temperature: float = Field(0.7, alias="ELEVENLABS_TEMPERATURE")
    speed: float = Field(1.0, alias="ELEVENLABS_SPEED")
    warmth: float = Field(0.75, alias="ELEVENLABS_WARMTH")
    stability: float = Field(0.7, alias="ELEVENLABS_STABILITY")
    similarity_boost: float = Field(0.75, alias="ELEVENLABS_SIMILARITY_BOOST")

    model_config = {"env_file": ".env", "extra": "ignore"}


class VoiceSettings(BaseSettings):
    """Voice Gateway Pipeline (VAD, STT, TTS, Fallbacks, Safety check-output)."""

    vad_model_path: str = Field("models/silero_vad.onnx", alias="VAD_MODEL_PATH")
    whisper_url: str = Field("http://localhost:8003", alias="WHISPER_URL")
    whisper_model: str = Field("faster-distil-whisper-large-v3", alias="WHISPER_MODEL")
    kokoro_url: str = Field("http://localhost:8004", alias="KOKORO_URL")
    kokoro_profile_hi: str = Field("hi_female", alias="KOKORO_PROFILE_HI")
    piper_path: str = Field("piper", alias="PIPER_PATH")
    piper_model_pa: str = Field("models/pa_in.onnx", alias="PIPER_MODEL_PA")
    temperature: float = Field(0.7, alias="VOICE_TEMPERATURE")
    speed: float = Field(1.0, alias="VOICE_SPEED")
    warmth: float = Field(0.75, alias="VOICE_WARMTH")
    voice_classifier_url: str = Field(
        "http://vllm-classifier-voice:8002", alias="VOICE_CLASSIFIER_URL"
    )
    orchestration_url: str = Field(
        "http://orchestration:8000", alias="ORCHESTRATION_URL"
    )
    gateway_url: str = Field("http://voice-gateway:8000", alias="VOICE_GATEWAY_URL")

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
    cors_allowed_origins: str = Field(
        "http://localhost:3000", alias="CORS_ALLOWED_ORIGINS"
    )
    internal_service_token: str = Field("", alias="INTERNAL_SERVICE_TOKEN")

    memory_db: MemoryDBSettings = MemoryDBSettings()  # type: ignore[call-arg]
    governance_db: GovernanceDBSettings = GovernanceDBSettings()  # type: ignore[call-arg]
    vllm: VLLMSettings = VLLMSettings()  # type: ignore[call-arg]
    safety_proxy: SafetyProxySettings = SafetyProxySettings()  # type: ignore[call-arg]
    governance: GovernanceServiceSettings = GovernanceServiceSettings()  # type: ignore[call-arg]
    ingestion: IngestionServiceSettings = IngestionServiceSettings()  # type: ignore[call-arg]
    dashboard: DashboardBFFSettings = DashboardBFFSettings()  # type: ignore[call-arg]
    langfuse: LangfuseSettings = LangfuseSettings()  # type: ignore[call-arg]
    minio: MinIOSettings = MinIOSettings()  # type: ignore[call-arg]
    auth: AuthSettings = AuthSettings()  # type: ignore[call-arg]
    escalation: EscalationSettings = EscalationSettings()  # type: ignore[call-arg]
    livekit: LiveKitSettings = LiveKitSettings()  # type: ignore[call-arg]
    groq: GroqSettings = GroqSettings()  # type: ignore[call-arg]
    elevenlabs: ElevenLabsSettings = ElevenLabsSettings()  # type: ignore[call-arg]
    voice: VoiceSettings = VoiceSettings()  # type: ignore[call-arg]
    panel: PanelSettings = PanelSettings()  # type: ignore[call-arg]
    mongodb: MongoDBSettings = MongoDBSettings()  # type: ignore[call-arg]
    supabase: SupabaseSettings = SupabaseSettings()  # type: ignore[call-arg]

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    def model_post_init(self, __context: object) -> None:
        if self.environment in {"pilot", "staging", "production"}:
            if self.auth.jwt_secret_key == "dev_secret_key":
                raise ValueError("JWT_SECRET_KEY must be set outside development")
            if self.livekit.api_key == "devkey" or self.livekit.api_secret == "secret":
                raise ValueError(
                    "LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set outside development"
                )
            if not self.internal_service_token:
                raise ValueError(
                    "INTERNAL_SERVICE_TOKEN must be set outside development"
                )

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance. Call this everywhere instead of os.environ."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()


def require_internal_service_token(token: str) -> None:
    """Validate service-to-service calls; development may remain hermetic."""
    if settings.is_dev:
        return
    if not settings.internal_service_token or not hmac.compare_digest(
        token, settings.internal_service_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )
