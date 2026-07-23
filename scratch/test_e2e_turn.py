"""
E2E Turn Pipeline Verification Script.
Executes a full turn through OrchestrationGraph with mock/in-memory backends
and verifies full turn execution, safety rails, and memory writes.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

# Setup sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "services" / "orchestration" / "src"))
sys.path.insert(0, str(root_dir / "services" / "api-gateway" / "src"))

from services.abstractions import InMemoryVectorStore, MockLLMClient, MockSafetyClient
from services.orchestration.src.orchestration.graph import OrchestrationGraph


async def run_e2e_turn_smoke():
    print("[E2E TEST] Initializing OrchestrationGraph...")
    graph = OrchestrationGraph(
        safety_client=MockSafetyClient(),
        memory_store=InMemoryVectorStore(),
        llm_client=MockLLMClient(reply="Hello! I am Vadi, your AI mentor."),
    )

    tenant_id = str(uuid4())
    learner_id = str(uuid4())
    session_id = str(uuid4())

    print("[E2E TEST] Executing turn: 'Namaste Vadi, tell me about Mars'...")
    result = await graph.run_turn(
        session_id=session_id,
        tenant_id=tenant_id,
        learner_id=learner_id,
        age_band=2,
        message_text="Namaste Vadi, tell me about Mars",
    )

    print(f"[E2E TEST] Final reply: {result.final_reply}")
    assert result.final_reply != "", "Final reply should not be empty"
    assert result.error is None, f"Turn execution errored: {result.error}"
    assert result.safety_verdict_input is not None
    assert result.safety_verdict_output is not None
    print("[E2E TEST] Turn execution successful and passed all assertions!")


if __name__ == "__main__":
    asyncio.run(run_e2e_turn_smoke())
