"""RLS-scoped dashboard read repository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg


class PostgresDashboardRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def learners(
        self, tenant_id: UUID, guardian_id: UUID
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                rows = await conn.fetch(
                    """
                    SELECT l.id AS learner_id, l.first_name AS display_name, l.age_band,
                           COUNT(ir.id) FILTER (WHERE ir.status = 'active')::int AS active_relationships_count,
                           MAX(m.created_at) AS last_session_at
                    FROM learners l
                    LEFT JOIN introduced_relationships ir ON ir.learner_id = l.id
                    LEFT JOIN learner_memories m ON m.learner_id = l.id
                    WHERE l.tenant_id = $1 AND l.guardian_id = $2 AND l.status = 'active'
                    GROUP BY l.id, l.first_name, l.age_band
                    ORDER BY l.created_at DESC
                    """,
                    tenant_id,
                    guardian_id,
                )
                return [dict(row) for row in rows]

    async def learner_count(self, tenant_id: UUID) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                return int(
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM learners WHERE tenant_id = $1 AND status = 'active'",
                        tenant_id,
                    )
                )
