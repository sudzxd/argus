"""Tests for ActionConfig."""

from __future__ import annotations

import textwrap

from pathlib import Path
from unittest.mock import patch

import pytest

from argus.interfaces.config import ActionConfig
from argus.shared.exceptions import ConfigurationError
from argus.shared.types import ReviewDepth


class TestActionConfig:
    def test_from_toml_with_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        # No pyproject.toml → all defaults
        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.github_token == "tok"
        assert config.github_repository == "org/repo"
        assert config.model == "anthropic:claude-sonnet-4-5-20250929"
        assert config.max_tokens == 128_000
        assert config.review_depth == ReviewDepth.STANDARD
        assert config.extra_extensions == []

    def test_from_toml_with_custom_review_depth(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [tool.argus]
                review_depth = "deep"
            """)
        )
        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert config.review_depth == ReviewDepth.DEEP

    def test_from_toml_with_extra_extensions(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")

        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [tool.argus]
                extra_extensions = [".vue", ".svelte", "proto"]
            """)
        )
        with patch("argus.interfaces.toml_config.Path.cwd", return_value=tmp_path):
            config = ActionConfig.from_toml()

        assert ".vue" in config.extra_extensions
        assert ".svelte" in config.extra_extensions
        assert ".proto" in config.extra_extensions

    def test_from_toml_missing_required_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with pytest.raises(ConfigurationError, match="GITHUB_TOKEN"):
            ActionConfig.from_toml()
