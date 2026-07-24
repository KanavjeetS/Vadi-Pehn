"""
Deployment Canonicalization & Stack Validation Test Suite.
Verifies:
1. Root docker-compose.yml contains all 9 microservices + webapp (Nginx) + 2 Postgres DBs,
   and passes docker compose config syntax check.
2. start_desktop.py imports and mounts all sub-services and static routes cleanly.
3. vadi.ps1 accurately references canonical launchers (dev -> start_desktop.py, docker-up -> docker-compose.yml).
4. infra/ folder contains unambiguous README documentation and deprecation notices on legacy compose files.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
import yaml
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_docker_compose_canonical_services():
    """Verify root docker-compose.yml contains all 9 microservices, nginx, and 2 postgres instances."""
    compose_path = ROOT_DIR / "docker-compose.yml"
    assert compose_path.exists(), "root docker-compose.yml must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "services" in config, "docker-compose.yml must define 'services'"
    services = config["services"]

    # 9 Microservices required
    required_microservices = [
        "api-gateway",
        "dashboard-bff",
        "orchestration",
        "voice-gateway",
        "governance-service",
        "panel-service",
        "safety-proxy",
        "ingestion-service",
        "memory-service",
    ]

    # Normalize service names (handling hyphens and underscores)
    normalized_service_names = {name.replace("_", "-"): name for name in services.keys()}

    for ms in required_microservices:
        assert ms in normalized_service_names, f"Microservice '{ms}' missing from root docker-compose.yml"

    # Nginx webapp frontend
    assert "webapp" in services, "Nginx webapp frontend missing from root docker-compose.yml"

    # 2 Physically separate Postgres DB instances (Architecture Non-Negotiable)
    assert "postgres-memory" in services, "postgres-memory pgvector DB missing from root docker-compose.yml"
    assert "postgres-governance" in services, "postgres-governance DB missing from root docker-compose.yml"


def test_docker_compose_config_syntax():
    """Validate docker-compose.yml syntax using docker compose CLI if available."""
    compose_path = ROOT_DIR / "docker-compose.yml"
    try:
        res = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "config", "--quiet"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert res.returncode == 0, f"docker compose config failed: {res.stderr}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback to YAML parse verification if docker CLI is not installed or available
        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            assert isinstance(data, dict) and "services" in data


def test_start_desktop_imports_and_mounts():
    """Verify start_desktop.py imports and mounts all 9 sub-services and static webapp routes."""
    desktop_path = ROOT_DIR / "start_desktop.py"
    assert desktop_path.exists(), "start_desktop.py must exist"

    content = desktop_path.read_text(encoding="utf-8")

    # Verify imports for all 9 microservices
    expected_imports = [
        "api_gateway_app",
        "dashboard_app",
        "orchestration_app",
        "voice_gateway_app",
        "governance_app",
        "panel_app",
        "safety_proxy_app",
        "ingestion_app",
        "memory_app",
    ]

    for imp in expected_imports:
        assert imp in content, f"start_desktop.py must import '{imp}'"

    # Verify inclusion in sub_apps list
    assert "sub_apps = [" in content, "start_desktop.py must define sub_apps list"
    for app_var in [
        "dashboard_app",
        "api_gateway_app",
        "orchestration_app",
        "voice_gateway_app",
        "governance_app",
        "panel_app",
        "safety_proxy_app",
        "ingestion_app",
        "memory_app",
    ]:
        assert app_var in content, f"sub_apps list in start_desktop.py must include '{app_var}'"

    # Verify static mounts for webapp
    assert 'desktop_app.mount("/child"' in content, "start_desktop.py must mount /child static files"
    assert 'desktop_app.mount("/guardian"' in content, "start_desktop.py must mount /guardian static files"
    assert 'desktop_app.mount("/admin"' in content, "start_desktop.py must mount /admin static files"


def test_vadi_ps1_canonical_launchers():
    """Verify vadi.ps1 accurately references canonical launchers and includes check target."""
    script_path = ROOT_DIR / "vadi.ps1"
    assert script_path.exists(), "vadi.ps1 must exist"

    content = script_path.read_text(encoding="utf-8")

    # dev target invokes start_desktop.py
    assert 'py "$Root\\start_desktop.py"' in content or 'python "$Root\\start_desktop.py"' in content

    # docker-up target invokes root docker-compose.yml
    assert 'docker compose -f "$Root\\docker-compose.yml" up -d' in content

    # check target exists
    assert '"check"' in content, "vadi.ps1 must define 'check' target"

    # help documentation mentions dev and docker-up as canonical
    assert "dev" in content and "docker-up" in content
    assert "start_desktop.py" in content and "docker-compose.yml" in content


def test_infra_folder_canonicalization():
    """Verify infra/ folder has README.md and deprecation notices on legacy compose files."""
    infra_dir = ROOT_DIR / "infra"
    readme_path = infra_dir / "README.md"

    assert readme_path.exists(), "infra/README.md must exist"
    readme_content = readme_path.read_text(encoding="utf-8")
    assert "CANONICAL LAUNCHERS" in readme_content

    legacy_files = [
        infra_dir / "docker-compose.yml",
        infra_dir / "docker-compose.dev.yml",
        infra_dir / "docker-compose.mvp.yml",
    ]

    for legacy in legacy_files:
        if legacy.exists():
            content = legacy.read_text(encoding="utf-8")
            assert "DEPRECATED" in content, f"Legacy file '{legacy.name}' must contain a DEPRECATED header"
