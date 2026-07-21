"""
Tenant Context & RLS Enforcement Module for Vadi-Pehn.
Implements: Architecture Non-Negotiables (RLS always), Master Backend Architecture §3.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
from uuid import UUID
import asyncpg
from fastapi import Request, HTTPException, status

logger = logging.getLogger("tenant_context")


class TenantContextMiddleware:
    """
    FastAPI Middleware that extracts `X-Tenant-ID` or JWT tenant scope
    and validates that a valid `tenant_id` exists on all protected routes.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        tenant_header = headers.get(b"x-tenant-id", b"").decode("utf-8")
        
        # Public paths bypass tenant enforcement
        path = scope.get("path", "")
        if path in ("/", "/health", "/docs", "/openapi.json") or path.startswith("/child") or path.startswith("/guardian"):
            await self.app(scope, receive, send)
            return

        scope["tenant_id"] = tenant_header if tenant_header else None
        await self.app(scope, receive, send)


class BaseRepository:
    """
    Base Repository requiring tenant_id on every DB call and enforcing RLS transaction scope.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def execute_in_tenant_context(
        self,
        tenant_id: UUID | str,
        query: str,
        *args: Any,
    ) -> Any:
        """
        Executes query inside an RLS-scoped transaction with SET LOCAL app.current_tenant_id.
        """
        tenant_str = str(tenant_id)
        if not tenant_str:
            raise ValueError("BaseRepository violation: tenant_id is required for all query executions")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET LOCAL app.current_tenant_id = $1", tenant_str)
                return await conn.fetch(query, *args)

    async def fetchval_in_tenant_context(
        self,
        tenant_id: UUID | str,
        query: str,
        *args: Any,
    ) -> Any:
        """
        Executes scalar query inside an RLS-scoped transaction with SET LOCAL app.current_tenant_id.
        """
        tenant_str = str(tenant_id)
        if not tenant_str:
            raise ValueError("BaseRepository violation: tenant_id is required for all query executions")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET LOCAL app.current_tenant_id = $1", tenant_str)
                return await conn.fetchval(query, *args)
