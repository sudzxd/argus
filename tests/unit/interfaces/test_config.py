"""Tests for ActionConfig."""

from __future__ import annotations

import pytest

from argus.interfaces.config import ActionConfig
from argus.shared.exceptions import ConfigurationError
from argus.shared.types import ReviewDepth


class TestActionConfig:
    def test_from_env_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        config = ActionConfig.from_env()

        assert config.github_token == "tok"
        assert config.github_repository == "org/repo"
        assert config.model == "anthropic:claude-sonnet-4-5-20250929"
        assert config.max_tokens == 128_000
        assert config.review_depth == ReviewDepth.STANDARD
        assert config.extra_extensions == []

    def test_from_env_with_custom_review_depth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")
        monkeypatch.setenv("INPUT_REVIEW_DEPTH", "deep")

        config = ActionConfig.from_env()

        assert config.review_depth == ReviewDepth.DEEP

    def test_from_env_with_extra_extensions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")
        monkeypatch.setenv("INPUT_EXTRA_EXTENSIONS", ".vue, .svelte, proto")

        config = ActionConfig.from_env()

        assert ".vue" in config.extra_extensions
        assert ".svelte" in config.extra_extensions
        assert ".proto" in config.extra_extensions

    def test_from_env_missing_required_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with pytest.raises(ConfigurationError, match="GITHUB_TOKEN"):
            ActionConfig.from_env()
