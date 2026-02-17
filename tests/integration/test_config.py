"""Tests for ActionConfig environment variable parsing."""

from __future__ import annotations

import pytest

from argus.interfaces.config import ActionConfig
from argus.shared.exceptions import ConfigurationError


class TestActionConfigDefaults:
    """Test that required fields are enforced and defaults work."""

    def test_config_from_env_with_all_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        config = ActionConfig.from_env()

        assert config.github_token == "ghp_test123"
        assert config.github_repository == "owner/repo"
        assert config.github_event_path == "/tmp/event.json"

    def test_config_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        config = ActionConfig.from_env()

        assert config.model == "anthropic:claude-sonnet-4-5-20250929"
        assert config.max_tokens == 128_000
        assert config.temperature == 0.0
        assert config.confidence_threshold == 0.7
        assert config.ignored_paths == []
        assert config.storage_dir == ".argus-artifacts"
        assert config.enable_agentic is False


class TestActionConfigOverrides:
    """Test that env var overrides work."""

    def test_model_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_MODEL", "openai:gpt-4o")

        config = ActionConfig.from_env()

        assert config.model == "openai:gpt-4o"

    def test_max_tokens_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_MAX_TOKENS", "64000")

        config = ActionConfig.from_env()

        assert config.max_tokens == 64_000

    def test_confidence_threshold_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_CONFIDENCE_THRESHOLD", "0.5")

        config = ActionConfig.from_env()

        assert config.confidence_threshold == 0.5

    def test_ignored_paths_comma_separated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_IGNORED_PATHS", "vendor/,dist/,*.min.js")

        config = ActionConfig.from_env()

        assert config.ignored_paths == ["vendor/", "dist/", "*.min.js"]

    def test_ignored_paths_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_IGNORED_PATHS", "")

        config = ActionConfig.from_env()

        assert config.ignored_paths == []

    def test_storage_dir_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_STORAGE_DIR", "/tmp/artifacts")

        config = ActionConfig.from_env()

        assert config.storage_dir == "/tmp/artifacts"

    def test_enable_agentic_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_ENABLE_AGENTIC", "true")

        config = ActionConfig.from_env()

        assert config.enable_agentic is True

    def test_enable_agentic_false_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_required(monkeypatch)
        monkeypatch.setenv("INPUT_ENABLE_AGENTIC", "false")

        config = ActionConfig.from_env()

        assert config.enable_agentic is False

    @staticmethod
    def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")


class TestActionConfigValidation:
    """Test validation for missing required fields."""

    def test_missing_github_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        with pytest.raises(ConfigurationError, match="GITHUB_TOKEN"):
            ActionConfig.from_env()

    def test_missing_github_repository_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        with pytest.raises(ConfigurationError, match="GITHUB_REPOSITORY"):
            ActionConfig.from_env()

    def test_missing_github_event_path_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with pytest.raises(ConfigurationError, match="GITHUB_EVENT_PATH"):
            ActionConfig.from_env()
