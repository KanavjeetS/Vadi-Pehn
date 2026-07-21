"""Production orchestration service composition and HTTP boundary."""

from __future__ import annotations

import os
import sys
import json
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
MEMORY_SRC = os.path.join(ROOT, "services", "memory-service", "src")
SAFETY_SRC = os.path.join(ROOT, "services", "safety-proxy", "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if MEMORY_SRC not in sys.path:
    sys.path.insert(0, MEMORY_SRC)
if SAFETY_SRC not in sys.path:
    sys.path.insert(0, SAFETY_SRC)

from memory_service.abstractions import ConsentCheckerClient  # noqa: E402
from memory_service.context import ContextualRetrievalService  # noqa: E402
from memory_service.embeddings import NomicEmbeddingClient  # noqa: E402
from memory_service.retrieval import HybridRetrievalEngine  # noqa: E402
from memory_service.store import PostgresMemoryStore  # noqa: E402
from memory_service.write_pipeline import AsyncMemoryWriter  # noqa: E402
from services.config import require_internal_service_token, settings  # noqa: E402
from orchestration.graph import (  # noqa: E402
    HttpGovernanceIncidentClient,
    OrchestrationGraph,
    TurnState,
)  # noqa: E402
from orchestration.llm_client import SafetyProxyLLMClient  # noqa: E402
from safety_proxy.client import NeMoSafetyClient  # noqa: E402


class HttpGovernanceConsentChecker(ConsentCheckerClient):
    """Read consent from Governance; unavailable means no memory write."""

    async def check_memory_write_consent(
        self, tenant_id: UUID, learner_id: UUID
    ) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{settings.governance.url.rstrip('/')}/internal/v1/governance/consent/{learner_id}",
                    headers={
                        "X-Tenant-ID": str(tenant_id),
                        "X-Internal-Service-Token": settings.internal_service_token,
                    },
                )
                response.raise_for_status()
                return bool(response.json().get("conversation_storage", False))
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return False


class OrchestrationTurnRequest(BaseModel):
    session_id: str
    tenant_id: UUID
    learner_id: UUID
    age_band: int = Field(ge=1, le=3)
    message_text: str = Field(min_length=1, max_length=12000)
    language: str = "en"


graph: OrchestrationGraph | None = None
pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global graph, pool
    pool = await asyncpg.create_pool(settings.memory_db.dsn, min_size=1, max_size=10)
    embedding_client = NomicEmbeddingClient(
        base_url=settings.memory_db.embedding_url,
        model=settings.memory_db.embedding_model,
    )
    retrieval = HybridRetrievalEngine(pool, embedding_client)
    graph = OrchestrationGraph(
        safety_client=NeMoSafetyClient(),
        memory_store=PostgresMemoryStore(pool),
        llm_client=SafetyProxyLLMClient(),
        embedding_client=embedding_client,
        context_service=ContextualRetrievalService(pool, retrieval),
        memory_writer=AsyncMemoryWriter(
            pool, HttpGovernanceConsentChecker(), embedding_client
        ),
        governance_client=HttpGovernanceIncidentClient(),
    )
    try:
        yield
    finally:
        graph = None
        await pool.close()
        pool = None


app = FastAPI(title="Vadi-Pehn Orchestration", version="0.2.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestration"}


@app.post("/internal/v1/orchestration/turn", response_model=TurnState)
async def run_turn(
    request: OrchestrationTurnRequest,
    x_internal_service_token: str = Header(default=""),
) -> TurnState:
    require_internal_service_token(x_internal_service_token)
    if graph is None:
        raise HTTPException(
            status_code=503, detail="orchestration runtime is not ready"
        )
    return await graph.run_turn(
        session_id=request.session_id,
        tenant_id=str(request.tenant_id),
        learner_id=str(request.learner_id),
        age_band=request.age_band,
        message_text=request.message_text,
        language=request.language,
    )


@app.post("/internal/v1/orchestration/stream")
async def stream_turn(
    request: OrchestrationTurnRequest,
    x_internal_service_token: str = Header(default=""),
):
    require_internal_service_token(x_internal_service_token)
    """Stream provider deltas for voice; each delta remains subject to voice output rails."""
    if graph is None:
        raise HTTPException(
            status_code=503, detail="orchestration runtime is not ready"
        )
    initial = TurnState(
        session_id=request.session_id,
        tenant_id=str(request.tenant_id),
        learner_id=str(request.learner_id),
        age_band=request.age_band,
        message_text=request.message_text,
        language_detected=request.language,
    )
    checked = await graph.check_input_safety(initial)

    async def events():
        if (checked.safety_verdict_input or {}).get("blocks_generation", True):
            safe_state = await graph.handle_unsafe_input(checked)
            yield f"data: {json.dumps({'delta': safe_state.final_reply})}\n\n"
            return
        async for delta in graph.stream_reply(checked):
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
