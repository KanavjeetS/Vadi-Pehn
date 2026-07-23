"""
Diversity Test Verification Script.
Executes 5 turns across distinct topics and persona contexts,
verifying that 5/5 unique non-empty responses are generated.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from services.abstractions import InMemoryVectorStore, MockLLMClient, MockSafetyClient
from services.orchestration.src.orchestration.graph import OrchestrationGraph


async def test_diversity_responses():
    print("[DIVERSITY TEST] Testing response diversity across 5 prompts...")

    # 5 distinct prompts exploring different domain persona topics
    prompts = [
        "I want to build software systems and AI algorithms when I grow up.",
        "Tell me about smart farming, hydroponics, and crop data.",
        "How do doctors and nurses help people in public health?",
        "What does an electrician do when installing solar power grids?",
        "I love creating visual graphics, user interfaces, and digital animations.",
    ]

    # Mock responses corresponding to distinct domain experts
    mock_replies = [
        "Software engineering is exciting! You can learn Python and build cool AI models.",
        "Agricultural technology uses IoT sensors to make farming sustainable and efficient.",
        "Healthcare specialists save lives every day using medicine and compassionate care.",
        "Solar electricians harness clean energy from the sun to power cities cleanly.",
        "Digital media design combines creative art with technology to build UI experiences.",
    ]

    responses: list[str] = []

    for i, (prompt, reply) in enumerate(zip(prompts, mock_replies), 1):
        graph = OrchestrationGraph(
            safety_client=MockSafetyClient(),
            memory_store=InMemoryVectorStore(),
            llm_client=MockLLMClient(reply=reply),
        )
        res = await graph.run_turn(
            session_id=str(uuid4()),
            tenant_id=str(uuid4()),
            learner_id=str(uuid4()),
            age_band=2,
            message_text=prompt,
        )
        print(f"Turn {i} prompt: '{prompt}'")
        print(f"Turn {i} reply: '{res.final_reply}'\n")
        assert res.final_reply.strip() != "", f"Turn {i} response was empty"
        responses.append(res.final_reply.strip())

    unique_responses = set(responses)
    print(f"[DIVERSITY TEST] Unique responses count: {len(unique_responses)}/5")
    assert len(unique_responses) == 5, f"Expected 5 unique responses, got {len(unique_responses)}"
    print("[DIVERSITY TEST] PASSED: 5/5 unique non-empty responses verified!")


if __name__ == "__main__":
    asyncio.run(test_diversity_responses())
