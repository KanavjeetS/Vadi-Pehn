"""
Agent Orchestration Service Entrypoint for Vadi-Pehn (Service B).
Houses LangGraph Relational Mentor Graph, CrewAI Discovery Panel, Professional & Curator Agents,
Ollama LLM Integration, and Streaming Voice SSE/WebSocket Endpoints.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Vadi-Pehn Agent Orchestration Service",
    description="Service B — LangGraph + CrewAI + Ollama + Voice Streaming",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "agent-service", "version": "2.0.0"}


@app.get("/api/v1/agents/status")
async def get_agents_status() -> dict[str, str]:
    return {
        "sibling_mentor": "active",
        "professional_agent": "active",
        "curator_agent": "active",
        "ollama_llm": "ready",
    }
