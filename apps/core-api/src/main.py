"""
Core API Service Entrypoint for Vadi-Pehn (Service A).
Handles authentication, tenant/user management, consent ledger, document upload intake,
and guardian dashboard read aggregation APIs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Vadi-Pehn Core API Service",
    description="Service A — Auth, Tenants, Uploads, Consent, Guardian Dashboard",
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
    return {"status": "ok", "service": "core-api", "version": "2.0.0"}


@app.get("/api/v1/auth/session")
async def get_session_info() -> dict[str, str]:
    return {"status": "authenticated", "scope": "learner"}
