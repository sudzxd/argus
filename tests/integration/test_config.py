"""Tests for ActionConfig with TOML configuration."""

from __future__ import annotations

import textwrap

from pathlib import Path
from unittest.mock import patch

import pytest

from argus.interfaces.config import ActionConfig
from argus.shared.exceptions import ConfigurationError


class TestActionConfigDefaults:
    """Test that required fields are enforced and defaults work."""

    def test_config_from_toml_with_all_required(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.github_token == "ghp_test123"
        assert config.github_repository == "owner/repo"
        assert config.github_event_path == "/tmp/event.json"

    def test_config_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.model == "anthropic:claude-sonnet-4-5-20250929"
        assert config.max_tokens == 128_000
        assert config.temperature == 0.0
        assert config.confidence_threshold == 0.7
        assert config.ignored_paths == []
        assert config.storage_dir == ".argus-artifacts"
        assert config.enable_agentic is False


class TestActionConfigOverrides:
    """Test that TOML overrides work."""

    @staticmethod
    def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

    @staticmethod
    def _write_toml(tmp_path: Path, content: str) -> None:
        (tmp_path / "pyproject.toml").write_text(textwrap.dedent(content))

    def test_model_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            model = "openai:gpt-4o"
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.model == "openai:gpt-4o"

    def test_max_tokens_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            max_tokens = 64000
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.max_tokens == 64_000

    def test_confidence_threshold_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            confidence_threshold = 0.5
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.confidence_threshold == 0.5

    def test_ignored_paths_array(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            ignored_paths = ["vendor/", "dist/", "*.min.js"]
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.ignored_paths == ["vendor/", "dist/", "*.min.js"]

    def test_ignored_paths_default_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.ignored_paths == []

    def test_storage_dir_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            storage_dir = "/tmp/artifacts"
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.storage_dir == "/tmp/artifacts"

    def test_enable_agentic_true(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            enable_agentic = true
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.enable_agentic is True

    def test_enable_agentic_false_explicit(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._set_required(monkeypatch)
        self._write_toml(
            tmp_path,
            """\
            [tool.argus]
            enable_agentic = false
        """,
        )

        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.enable_agentic is False


class TestActionConfigValidation:
    """Test validation for missing required fields."""

    def test_missing_github_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        with pytest.raises(ConfigurationError, match="GITHUB_TOKEN"):
            ActionConfig.from_toml()

    def test_missing_github_repository_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        with pytest.raises(ConfigurationError, match="GITHUB_REPOSITORY"):
            ActionConfig.from_toml()

    def test_missing_github_event_path_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with pytest.raises(ConfigurationError, match="GITHUB_EVENT_PATH"):
            ActionConfig.from_toml()
