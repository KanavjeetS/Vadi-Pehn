"""Hermetic evaluation defaults; production safety settings remain fail-closed."""

import pytest

from services.config import settings


@pytest.fixture(autouse=True)
def enable_explicit_eval_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.safety_proxy, "allow_dev_bypass", True)
