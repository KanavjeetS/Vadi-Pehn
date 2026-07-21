"""Static deployment guard for the Safety Proxy network boundary.

Implements: AGENTS Part 2, GUARDRAILS G-001, SystemDesign §6.1/§6.2.
This test does not prove a live Docker/Kubernetes policy; it prevents the
checked-in desktop/MVP manifests from publishing vLLM directly to a host.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _manifest_text(name: str) -> str:
    return (ROOT / "infra" / name).read_text(encoding="utf-8")


def test_dev_vllm_services_are_not_host_published() -> None:
    text = _manifest_text("docker-compose.dev.yml")
    main_block = text.split("  vllm-main-stub:", 1)[1].split(
        "  vllm-classifier-stub:", 1
    )[0]
    classifier_block = text.split("  vllm-classifier-stub:", 1)[1]
    assert "expose:" in main_block and '"8001"' in main_block
    assert '"8001:8001"' not in main_block
    assert "expose:" in classifier_block and '"8002"' in classifier_block
    assert '"8002:8002"' not in classifier_block


def test_mvp_main_vllm_has_only_backend_network() -> None:
    text = _manifest_text("docker-compose.mvp.yml")
    main_block = text.split("  vllm-main:", 1)[1].split("  vllm-classifier:", 1)[0]
    assert "expose:" in main_block
    assert '"8001:8000"' not in main_block
    assert "vadi-llm-backend" in main_block
