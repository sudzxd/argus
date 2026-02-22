"""Tests for env_utils shared helpers."""

from __future__ import annotations

import pytest

from argus.interfaces.env_utils import require_env
from argus.shared.exceptions import ConfigurationError


def test_require_env_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_VAR", "hello")
    assert require_env("TEST_VAR") == "hello"


def test_require_env_raises_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_VAR_MISSING", raising=False)
    with pytest.raises(ConfigurationError, match="TEST_VAR_MISSING"):
        require_env("TEST_VAR_MISSING")


def test_require_env_raises_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_VAR_EMPTY", "")
    with pytest.raises(ConfigurationError, match="TEST_VAR_EMPTY"):
        require_env("TEST_VAR_EMPTY")
