"""Persistent guardian/learner identity repository and explicit test double."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg


class IdentityStore(ABC):
    @abstractmethod
    async def create_guardian(
        self,
        *,
        tenant_id: UUID,
        guardian_name: str,
        phone_number: str,
        verification_method: str,
        verified: bool,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def create_learner(
        self,
        *,
        tenant_id: UUID,
        guardian_id: UUID,
        display_name: str,
        age_band: int,
        preferred_language: str,
    ) -> dict[str, Any]: ...


class PostgresIdentityStore(IdentityStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_guardian(
        self,
        *,
        tenant_id: UUID,
        guardian_name: str,
        phone_number: str,
        verification_method: str,
        verified: bool,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                await conn.execute(
                    "INSERT INTO tenants (id, name, region) VALUES ($1, $2, 'in') ON CONFLICT (id) DO NOTHING",
                    tenant_id,
                    guardian_name,
                )
                guardian_id = await conn.fetchval(
                    """
                    INSERT INTO guardians (tenant_id, phone_number, verification_method, verified_at)
                    VALUES ($1, $2, $3, $4) RETURNING id
                    """,
                    tenant_id,
                    phone_number,
                    verification_method,
                    datetime.now(timezone.utc) if verified else None,
                )
                return {
                    "guardian_id": str(guardian_id),
                    "tenant_id": str(tenant_id),
                    "verification_status": "verified" if verified else "pending",
                }

    async def create_learner(
        self,
        *,
        tenant_id: UUID,
        guardian_id: UUID,
        display_name: str,
        age_band: int,
        preferred_language: str,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                learner_id = await conn.fetchval(
                    """
                    INSERT INTO learners (tenant_id, guardian_id, first_name, age_band, preferred_language)
                    VALUES ($1, $2, $3, $4, $5) RETURNING id
                    """,
                    tenant_id,
                    guardian_id,
                    display_name,
                    age_band,
                    preferred_language,
                )
                return {
                    "learner_id": str(learner_id),
                    "tenant_id": str(tenant_id),
                    "guardian_id": str(guardian_id),
                    "display_name": display_name,
                }


class InMemoryIdentityStore(IdentityStore):
    """Test-only repository; application runtime never selects this implementation."""

    def __init__(self) -> None:
        self.guardians: dict[str, dict[str, Any]] = {}
        self.learners: dict[str, dict[str, Any]] = {}

    async def create_guardian(
        self,
        *,
        tenant_id: UUID,
        guardian_name: str,
        phone_number: str,
        verification_method: str,
        verified: bool,
    ) -> dict[str, Any]:
        guardian_id = uuid4()
        record = {
            "guardian_id": str(guardian_id),
            "tenant_id": str(tenant_id),
            "verification_status": "verified" if verified else "pending",
        }
        self.guardians[str(guardian_id)] = record
        return record

    async def create_learner(
        self,
        *,
        tenant_id: UUID,
        guardian_id: UUID,
        display_name: str,
        age_band: int,
        preferred_language: str,
    ) -> dict[str, Any]:
        learner_id = uuid4()
        record = {
            "learner_id": str(learner_id),
            "tenant_id": str(tenant_id),
            "guardian_id": str(guardian_id),
            "display_name": display_name,
        }
        self.learners[str(learner_id)] = record
        return record
