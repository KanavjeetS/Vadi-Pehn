"""
Retention Scheduler and Data Lifecycle Engine.
Implements: PRD §3.4 (18-Month Memory Expiry & Consent Withdrawal Purge).
"""

from __future__ import annotations

from typing import Callable, Awaitable
from uuid import UUID

from governance_service.abstractions import RetentionSchedulerEngine


class RetentionJobScheduler(RetentionSchedulerEngine):
    """
    Manages memory retention policies, nightly 18-month pruning, and consent revocation purges.
    """

    def __init__(
        self,
        memory_prune_callback: Callable[[int], Awaitable[int]] | None = None,
        memory_delete_callback: Callable[[UUID], Awaitable[int]] | None = None,
    ) -> None:
        self.memory_prune_callback = memory_prune_callback
        self.memory_delete_callback = memory_delete_callback

    async def prune_expired_memories(self, *, retention_days: int = 540) -> int:
        """
        PRD §3.4: Prunes learner memories older than 18 months (540 days).
        """
        if self.memory_prune_callback:
            return await self.memory_prune_callback(retention_days)
        return 0

    async def execute_immediate_consent_purge(self, *, learner_id: UUID) -> int:
        """
        PRD §3.4: Immediately deletes ALL memory records for a learner upon consent withdrawal.
        """
        if self.memory_delete_callback:
            return await self.memory_delete_callback(learner_id)
        return 0
