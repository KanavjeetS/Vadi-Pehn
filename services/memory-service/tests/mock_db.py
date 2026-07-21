"""
Mock asyncpg pool and connection classes for unit tests.
Extends the patterns used in test_store.py to support custom queries, fetches, and returns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


class MockAsyncpgTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class MockAsyncpgConnection:
    def __init__(self) -> None:
        self.executed_queries: list[tuple[str, tuple]] = []
        self.fetched_queries: list[tuple[str, tuple]] = []
        self.fetchval_queries: list[tuple[str, tuple]] = []
        self.current_settings: dict[str, str] = {}
        # Allows tests to define custom return values for fetch and fetchval
        self.fetch_returns: list[Any] = []
        self.fetchval_returns: list[Any] = []
        self.fetch_callback: Callable[[str, tuple], Any] | None = None

    def transaction(self) -> MockAsyncpgTransaction:
        return MockAsyncpgTransaction()

    async def execute(self, query: str, *args) -> str:
        self.executed_queries.append((query.strip(), args))
        if query.strip().startswith("SET LOCAL app.current_tenant_id ="):
            self.current_settings["app.current_tenant_id"] = args[0]
        return "OK"

    async def fetchval(self, query: str, *args) -> Any:
        self.fetchval_queries.append((query.strip(), args))
        if self.fetchval_returns:
            return self.fetchval_returns.pop(0)
        return 12345

    async def fetch(self, query: str, *args) -> list[dict[str, Any]]:
        self.fetched_queries.append((query.strip(), args))
        if self.fetch_callback:
            return self.fetch_callback(query, args)
        if self.fetch_returns:
            return self.fetch_returns.pop(0)
        return [
            {
                "id": uuid4(),
                "tenant_id": uuid4(),
                "learner_id": uuid4(),
                "content": "Mock memory text",
                "metadata": "{}",
                "created_at": datetime.now(timezone.utc),
                "similarity_score": 0.95,
            }
        ]


class MockAsyncpgPoolContext:
    def __init__(self, conn: MockAsyncpgConnection) -> None:
        self.conn = conn

    async def __aenter__(self) -> MockAsyncpgConnection:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        pass


class MockAsyncpgPool:
    def __init__(self, conn: MockAsyncpgConnection | None = None) -> None:
        self.conn = conn or MockAsyncpgConnection()

    def acquire(self) -> MockAsyncpgPoolContext:
        return MockAsyncpgPoolContext(self.conn)
