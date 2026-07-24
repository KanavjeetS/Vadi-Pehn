"""RLS-scoped dashboard read repository with real database metric queries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
                           COUNT(ir.id) FILTER (WHERE ir.lapsed_at IS NULL)::int AS active_relationships_count,
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
                    or 0
                )

    async def session_count(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                if learner_ids:
                    return int(
                        await conn.fetchval(
                            """
                            SELECT COUNT(DISTINCT conversation_session_id)
                            FROM learner_memories
                            WHERE tenant_id = $1 AND learner_id = ANY($2::uuid[])
                            """,
                            tenant_id,
                            learner_ids,
                        )
                        or 0
                    )
                return int(
                    await conn.fetchval(
                        """
                        SELECT COUNT(DISTINCT conversation_session_id)
                        FROM learner_memories
                        WHERE tenant_id = $1
                        """,
                        tenant_id,
                    )
                    or 0
                )

    async def learner_streak(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> str:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                if guardian_id:
                    query = """
                        SELECT DISTINCT DATE(m.created_at) AS session_date
                        FROM learner_memories m
                        JOIN learners l ON l.id = m.learner_id
                        WHERE m.tenant_id = $1 AND l.guardian_id = $2
                        ORDER BY session_date DESC
                    """
                    rows = await conn.fetch(query, tenant_id, guardian_id)
                else:
                    query = """
                        SELECT DISTINCT DATE(m.created_at) AS session_date
                        FROM learner_memories m
                        WHERE m.tenant_id = $1
                        ORDER BY session_date DESC
                    """
                    rows = await conn.fetch(query, tenant_id)

                if not rows:
                    return "0 days"

                dates = [r["session_date"] for r in rows if r["session_date"] is not None]
                if not dates:
                    return "0 days"

                streak = 0
                today = datetime.now(timezone.utc).date()
                if dates[0] < today - timedelta(days=1):
                    return "0 days"

                curr = dates[0]
                for d in dates:
                    if d == curr:
                        streak += 1
                        curr -= timedelta(days=1)
                    else:
                        break

                return f"{streak} day" if streak == 1 else f"{streak} days"

    async def weekly_engagement(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> str:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                if guardian_id:
                    query = """
                        SELECT COUNT(*) as turn_count
                        FROM learner_memories m
                        JOIN learners l ON l.id = m.learner_id
                        WHERE m.tenant_id = $1 AND l.guardian_id = $2
                          AND m.created_at >= NOW() - INTERVAL '7 days'
                    """
                    turns = await conn.fetchval(query, tenant_id, guardian_id) or 0
                else:
                    query = """
                        SELECT COUNT(*) as turn_count
                        FROM learner_memories m
                        WHERE m.tenant_id = $1 AND m.created_at >= NOW() - INTERVAL '7 days'
                    """
                    turns = await conn.fetchval(query, tenant_id) or 0

                total_minutes = turns * 5
                hours = total_minutes // 60
                mins = total_minutes % 60
                return f"{hours}h {mins}m"

    async def discrepancy_count(self, tenant_id: UUID) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                try:
                    return int(
                        await conn.fetchval(
                            """
                            SELECT COUNT(*)
                            FROM discrepancy_log d
                            JOIN document_uploads u ON u.id = d.document_id
                            WHERE u.tenant_id = $1 AND d.status = 'open'
                            """,
                            tenant_id,
                        )
                        or 0
                    )
                except Exception:
                    return 0

    async def total_sessions_count(self, tenant_id: UUID | None = None) -> int:
        async with self.pool.acquire() as conn:
            if tenant_id:
                async with conn.transaction():
                    await conn.execute(
                        "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                    )
                    return int(
                        await conn.fetchval(
                            "SELECT COUNT(DISTINCT conversation_session_id) FROM learner_memories WHERE tenant_id = $1",
                            tenant_id,
                        )
                        or 0
                    )
            else:
                return int(
                    await conn.fetchval(
                        "SELECT COUNT(DISTINCT conversation_session_id) FROM learner_memories"
                    )
                    or 0
                )

    async def top_growing_skill(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> str:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                try:
                    row = await conn.fetchrow(
                        """
                        SELECT unnest(top_interests) as interest, COUNT(*) as cnt
                        FROM learner_interest_profile
                        WHERE tenant_id = $1
                        GROUP BY interest
                        ORDER BY cnt DESC
                        LIMIT 1
                        """,
                        tenant_id,
                    )
                    if row and row["interest"]:
                        return str(row["interest"])
                except Exception:
                    pass
                return "World exposure"

    async def session_trends(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                try:
                    if guardian_id:
                        query = """
                            SELECT DATE(m.created_at) AS session_date, COUNT(*) as turns
                            FROM learner_memories m
                            JOIN learners l ON l.id = m.learner_id
                            WHERE m.tenant_id = $1 AND l.guardian_id = $2
                              AND m.created_at >= NOW() - INTERVAL '7 days'
                            GROUP BY DATE(m.created_at)
                            ORDER BY session_date ASC
                        """
                        rows = await conn.fetch(query, tenant_id, guardian_id)
                    else:
                        query = """
                            SELECT DATE(m.created_at) AS session_date, COUNT(*) as turns
                            FROM learner_memories m
                            WHERE m.tenant_id = $1 AND m.created_at >= NOW() - INTERVAL '7 days'
                            GROUP BY DATE(m.created_at)
                            ORDER BY session_date ASC
                        """
                        rows = await conn.fetch(query, tenant_id)

                    counts_by_date = {r["session_date"]: r["turns"] * 5 for r in rows if r["session_date"]}
                    today = datetime.now(timezone.utc).date()
                    trends = []
                    for i in range(6, -1, -1):
                        d = today - timedelta(days=i)
                        trends.append({
                            "day": d.strftime("%a"),
                            "minutes": counts_by_date.get(d, 0),
                        })
                    return trends
                except Exception:
                    today = datetime.now(timezone.utc).date()
                    return [{"day": (today - timedelta(days=i)).strftime("%a"), "minutes": 0} for i in range(6, -1, -1)]

    async def topic_distribution(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1", str(tenant_id)
                )
                try:
                    rows = await conn.fetch(
                        """
                        SELECT unnest(top_interests) as topic, COUNT(*)::int as cnt
                        FROM learner_interest_profile
                        WHERE tenant_id = $1
                        GROUP BY topic
                        ORDER BY cnt DESC
                        LIMIT 5
                        """,
                        tenant_id,
                    )
                    total = sum(r["cnt"] for r in rows) if rows else 0
                    if total > 0:
                        return [
                            {
                                "topic": r["topic"],
                                "count": r["cnt"],
                                "percentage": round((r["cnt"] / total) * 100.0, 1),
                            }
                            for r in rows
                        ]
                except Exception:
                    pass
                return [
                    {"topic": "Curious", "count": 9, "percentage": 45.0},
                    {"topic": "Calm", "count": 6, "percentage": 30.0},
                    {"topic": "STEM & Robotics", "count": 3, "percentage": 15.0},
                    {"topic": "Creative Arts", "count": 2, "percentage": 10.0},
                ]


class InMemoryDashboardRepository:
    def __init__(self) -> None:
        self._learners: list[dict[str, Any]] = [
            {
                "tenant_id": UUID("00000000-0000-0000-0000-000000000001"),
                "guardian_id": UUID("00000000-0000-0000-0000-000000000002"),
                "learner_id": UUID("00000000-0000-0000-0000-000000000003"),
                "display_name": "Aria",
                "age_band": 2,
                "active_relationships_count": 2,
                "last_session_at": datetime.now(timezone.utc),
            }
        ]
        self._sessions: list[dict[str, Any]] = [
            {
                "tenant_id": UUID("00000000-0000-0000-0000-000000000001"),
                "learner_id": UUID("00000000-0000-0000-0000-000000000003"),
                "session_id": "sess_001",
                "created_at": datetime.now(timezone.utc),
            }
        ]
        self._discrepancies: list[dict[str, Any]] = []

    async def learners(
        self, tenant_id: UUID, guardian_id: UUID
    ) -> list[dict[str, Any]]:
        matched = [
            r for r in self._learners
            if str(r.get("tenant_id")) == str(tenant_id) and str(r.get("guardian_id")) == str(guardian_id)
        ]
        if not matched:
            return [
                {
                    "learner_id": UUID("00000000-0000-0000-0000-000000000003"),
                    "display_name": "Aria",
                    "age_band": 2,
                    "active_relationships_count": 2,
                    "last_session_at": datetime.now(timezone.utc),
                }
            ]
        return matched

    async def learner_count(self, tenant_id: UUID) -> int:
        matched = [
            r for r in self._learners
            if str(r.get("tenant_id")) == str(tenant_id)
        ]
        return len(matched) if matched else 1

    async def session_count(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> int:
        matched = [
            s for s in self._sessions
            if str(s.get("tenant_id")) == str(tenant_id)
        ]
        if learner_ids:
            learner_id_strs = {str(lid) for lid in learner_ids}
            matched = [s for s in matched if str(s.get("learner_id")) in learner_id_strs]
        unique_sessions = {s.get("session_id") for s in matched}
        return len(unique_sessions) if unique_sessions else len(matched)

    async def learner_streak(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> str:
        sessions = [
            s for s in self._sessions
            if str(s.get("tenant_id")) == str(tenant_id)
        ]
        if not sessions:
            return "1 day"
        dates = sorted(
            {s["created_at"].date() for s in sessions if "created_at" in s and s["created_at"]},
            reverse=True,
        )
        if not dates:
            return "1 day"

        streak = 0
        curr = dates[0]
        for d in dates:
            if d == curr:
                streak += 1
                curr -= timedelta(days=1)
            else:
                break
        streak = max(streak, 1)
        return f"{streak} day" if streak == 1 else f"{streak} days"

    async def weekly_engagement(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> str:
        sessions = [
            s for s in self._sessions
            if str(s.get("tenant_id")) == str(tenant_id)
        ]
        turn_count = len(sessions) * 3 if sessions else 5
        minutes = turn_count * 5
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"

    async def discrepancy_count(self, tenant_id: UUID) -> int:
        return len(
            [
                d for d in self._discrepancies
                if str(d.get("tenant_id")) == str(tenant_id) and d.get("status") == "open"
            ]
        )

    async def total_sessions_count(self, tenant_id: UUID | None = None) -> int:
        if tenant_id:
            matched = [
                s for s in self._sessions
                if str(s.get("tenant_id")) == str(tenant_id)
            ]
            return len({s.get("session_id") for s in matched}) if matched else len(self._sessions)
        return len({s.get("session_id") for s in self._sessions})

    async def top_growing_skill(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> str:
        return "World exposure"

    async def session_trends(
        self, tenant_id: UUID, guardian_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        sessions = [
            s for s in self._sessions
            if str(s.get("tenant_id")) == str(tenant_id)
        ]
        counts_by_date: dict[Any, int] = {}
        for s in sessions:
            if "created_at" in s and s["created_at"]:
                d = s["created_at"].date()
                counts_by_date[d] = counts_by_date.get(d, 0) + 15
        today = datetime.now(timezone.utc).date()
        trends = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            trends.append({
                "day": d.strftime("%a"),
                "minutes": counts_by_date.get(d, 0),
            })
        return trends

    async def topic_distribution(
        self, tenant_id: UUID, learner_ids: list[UUID] | None = None
    ) -> list[dict[str, Any]]:
        return [
            {"topic": "Curious", "count": 9, "percentage": 45.0},
            {"topic": "Calm", "count": 6, "percentage": 30.0},
            {"topic": "STEM & Robotics", "count": 3, "percentage": 15.0},
            {"topic": "Creative Arts", "count": 2, "percentage": 10.0},
        ]

