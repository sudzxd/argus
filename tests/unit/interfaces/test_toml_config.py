"""Tests for TOML configuration loader."""

from __future__ import annotations

import logging
import textwrap

from pathlib import Path

import pytest

from argus.interfaces.toml_config import ArgusConfig, load_argus_config
from argus.shared.exceptions import ConfigurationError
from argus.shared.types import ReviewDepth


def _write_toml(tmp_path: Path, content: str) -> Path:
    """Write a pyproject.toml in *tmp_path* and return its parent dir."""
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent(content))
    return tmp_path


# =============================================================================
# Default behaviour (no pyproject.toml)
# =============================================================================


class TestDefaults:
    def test_load_no_pyproject_uses_review_defaults(self, tmp_path: Path) -> None:
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.model == "anthropic:claude-sonnet-4-5-20250929"
        assert cfg.max_tokens == 128_000

    def test_load_no_pyproject_uses_index_defaults(self, tmp_path: Path) -> None:
        cfg = load_argus_config("index", project_root=tmp_path)
        assert cfg.model == "google-gla:gemini-2.5-flash"
        assert cfg.max_tokens == 1_000_000

    def test_load_empty_tool_section_uses_defaults(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [project]
            name = "foo"
        """,
        )
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.model == "anthropic:claude-sonnet-4-5-20250929"
        assert cfg.temperature == 0.0
        assert cfg.confidence_threshold == 0.7

    def test_load_empty_argus_section_uses_defaults(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
        """,
        )
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.model == "anthropic:claude-sonnet-4-5-20250929"

    def test_load_common_defaults_applied(self, tmp_path: Path) -> None:
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.storage_dir == ".argus-artifacts"
        assert cfg.enable_agentic is False
        assert cfg.review_depth == ReviewDepth.STANDARD
        assert cfg.enable_pr_context is True
        assert cfg.search_related_issues is False
        assert cfg.embedding_model == ""
        assert cfg.analyze_patterns is False
        assert cfg.ignored_paths == []
        assert cfg.extra_extensions == []

    def test_load_bootstrap_uses_index_defaults(self, tmp_path: Path) -> None:
        cfg = load_argus_config("bootstrap", project_root=tmp_path)
        assert cfg.model == "google-gla:gemini-2.5-flash"
        assert cfg.max_tokens == 1_000_000


# =============================================================================
# TOML overrides
# =============================================================================


class TestOverrides:
    def test_load_overrides_from_toml(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            model = "openai:gpt-4o"
            max_tokens = 64000
            temperature = 0.5
            confidence_threshold = 0.9
            storage_dir = "custom-dir"
            enable_agentic = true
            review_depth = "deep"
            enable_pr_context = false
            search_related_issues = true
            embedding_model = "local:all-MiniLM-L6-v2"
            analyze_patterns = true
        """,
        )
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.model == "openai:gpt-4o"
        assert cfg.max_tokens == 64000
        assert cfg.temperature == 0.5
        assert cfg.confidence_threshold == 0.9
        assert cfg.storage_dir == "custom-dir"
        assert cfg.enable_agentic is True
        assert cfg.review_depth == ReviewDepth.DEEP
        assert cfg.enable_pr_context is False
        assert cfg.search_related_issues is True
        assert cfg.embedding_model == "local:all-MiniLM-L6-v2"
        assert cfg.analyze_patterns is True

    def test_load_index_subsection_overrides_in_index_mode(
        self, tmp_path: Path
    ) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            model = "openai:gpt-4o"
            max_tokens = 64000

            [tool.argus.index]
            model = "google-gla:gemini-2.5-flash"
            max_tokens = 1000000
        """,
        )
        cfg = load_argus_config("index", project_root=tmp_path)
        assert cfg.model == "google-gla:gemini-2.5-flash"
        assert cfg.max_tokens == 1_000_000

    def test_load_index_subsection_ignored_in_review_mode(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            model = "openai:gpt-4o"
            max_tokens = 64000

            [tool.argus.index]
            model = "google-gla:gemini-2.5-flash"
            max_tokens = 1000000
        """,
        )
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.model == "openai:gpt-4o"
        assert cfg.max_tokens == 64000


# =============================================================================
# Array / extension handling
# =============================================================================


class TestArraysAndExtensions:
    def test_load_arrays_parsed_natively(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            ignored_paths = ["docs/**", "*.md"]
        """,
        )
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.ignored_paths == ["docs/**", "*.md"]

    def test_load_extensions_normalized(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            extra_extensions = ["vue", ".svelte", "proto"]
        """,
        )
        cfg = load_argus_config("review", project_root=tmp_path)
        assert cfg.extra_extensions == [".vue", ".svelte", ".proto"]


# =============================================================================
# Validation
# =============================================================================


class TestValidation:
    def test_load_invalid_review_depth_raises(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            review_depth = "super-deep"
        """,
        )
        with pytest.raises(ConfigurationError, match="review_depth"):
            load_argus_config("review", project_root=tmp_path)

    def test_load_temperature_out_of_range_raises(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            temperature = 3.0
        """,
        )
        with pytest.raises(ConfigurationError, match="temperature"):
            load_argus_config("review", project_root=tmp_path)

    def test_load_confidence_threshold_out_of_range_raises(
        self, tmp_path: Path
    ) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            confidence_threshold = 1.5
        """,
        )
        with pytest.raises(ConfigurationError, match="confidence_threshold"):
            load_argus_config("review", project_root=tmp_path)

    def test_load_invalid_toml_raises(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("{{invalid toml")
        with pytest.raises(ConfigurationError, match="Failed to parse"):
            load_argus_config("review", project_root=tmp_path)

    def test_load_unknown_keys_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus]
            model = "openai:gpt-4o"
            unknown_key = true
        """,
        )
        with caplog.at_level(logging.WARNING, logger="argus.interfaces.toml_config"):
            load_argus_config("review", project_root=tmp_path)
        assert "unknown_key" in caplog.text

    def test_load_unknown_key_in_index_subsection_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _write_toml(
            tmp_path,
            """\
            [tool.argus.index]
            bogus = 42
        """,
        )
        with caplog.at_level(logging.WARNING, logger="argus.interfaces.toml_config"):
            load_argus_config("index", project_root=tmp_path)
        assert "bogus" in caplog.text


# =============================================================================
# ArgusConfig dataclass
# =============================================================================


class TestArgusConfigFrozen:
    def test_argus_config_is_frozen(self) -> None:
        cfg = ArgusConfig(model="m", max_tokens=100)
        with pytest.raises(AttributeError):
            cfg.model = "other"  # type: ignore[misc]
