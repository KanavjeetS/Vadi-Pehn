"""
FastAPI entry point for the Memory Service.
Implements: SD §3.2 (Conversational Memory with pgvector + RLS), SD §4.1.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory_service.store import PostgresMemoryStore
from services.abstractions import InMemoryVectorStore
from services.config import settings
from services.logging_config import configure_logging

configure_logging("memory-service")

memory_store: PostgresMemoryStore | InMemoryVectorStore | None = None
memory_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global memory_store, memory_pool
    if settings.is_dev:
        memory_store = InMemoryVectorStore()
        try:
            yield
        finally:
            memory_store = None
        return

    memory_pool = await asyncpg.create_pool(settings.memory_db.dsn, min_size=1, max_size=5)
    memory_store = PostgresMemoryStore(memory_pool)
    try:
        yield
    finally:
        memory_store = None
        if memory_pool:
            await memory_pool.close()
            memory_pool = None


app = FastAPI(
    title="Vadi-Pehn Memory Service",
    description="Conversational Memory microservice with pgvector + RLS isolation.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/healthz")
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "memory-service"}
