"""Configuration assembly from environment variables."""

from __future__ import annotations

import os

from dataclasses import dataclass, field

from argus.shared.exceptions import ConfigurationError
from argus.shared.types import ReviewDepth


def _require_env(name: str) -> str:
    """Read a required environment variable or raise."""
    value = os.environ.get(name)
    if not value:
        msg = f"Missing required environment variable: {name}"
        raise ConfigurationError(msg)
    return value


def _parse_int(name: str, raw: str) -> int:
    """Parse an integer env var or raise with a clear message."""
    try:
        return int(raw)
    except ValueError:
        msg = f"Invalid integer for {name}: {raw!r}"
        raise ConfigurationError(msg) from None


def _parse_float(name: str, raw: str) -> float:
    """Parse a float env var or raise with a clear message."""
    try:
        return float(raw)
    except ValueError:
        msg = f"Invalid float for {name}: {raw!r}"
        raise ConfigurationError(msg) from None


@dataclass(frozen=True)
class ActionConfig:
    """Typed configuration for the Argus GitHub Action."""

    github_token: str
    github_repository: str
    github_event_path: str
    model: str = "anthropic:claude-sonnet-4-5-20250929"
    max_tokens: int = 128_000
    temperature: float = 0.0
    confidence_threshold: float = 0.7
    ignored_paths: list[str] = field(default_factory=list[str])
    storage_dir: str = ".argus-artifacts"
    enable_agentic: bool = False
    review_depth: ReviewDepth = ReviewDepth.STANDARD
    extra_extensions: list[str] = field(default_factory=list[str])
    enable_pr_context: bool = True
    search_related_issues: bool = False
    embedding_model: str = ""

    @classmethod
    def from_env(cls) -> ActionConfig:
        """Build config from environment variables.

        Required:
            GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_EVENT_PATH

        Optional (with defaults):
            INPUT_MODEL, INPUT_MAX_TOKENS, INPUT_CONFIDENCE_THRESHOLD,
            INPUT_IGNORED_PATHS, INPUT_STORAGE_DIR, INPUT_ENABLE_AGENTIC
        """
        raw_ignored = os.environ.get("INPUT_IGNORED_PATHS", "")
        ignored = [p.strip() for p in raw_ignored.split(",") if p.strip()]

        return cls(
            github_token=_require_env("GITHUB_TOKEN"),
            github_repository=_require_env("GITHUB_REPOSITORY"),
            github_event_path=_require_env("GITHUB_EVENT_PATH"),
            model=os.environ.get("INPUT_MODEL", "anthropic:claude-sonnet-4-5-20250929"),
            max_tokens=_parse_int(
                "INPUT_MAX_TOKENS",
                os.environ.get("INPUT_MAX_TOKENS", "128000"),
            ),
            temperature=_parse_float(
                "INPUT_TEMPERATURE",
                os.environ.get("INPUT_TEMPERATURE", "0.0"),
            ),
            confidence_threshold=_parse_float(
                "INPUT_CONFIDENCE_THRESHOLD",
                os.environ.get("INPUT_CONFIDENCE_THRESHOLD", "0.7"),
            ),
            ignored_paths=ignored,
            storage_dir=os.environ.get("INPUT_STORAGE_DIR", ".argus-artifacts"),
            enable_agentic=os.environ.get("INPUT_ENABLE_AGENTIC", "false").lower()
            == "true",
            review_depth=ReviewDepth(os.environ.get("INPUT_REVIEW_DEPTH", "standard")),
            extra_extensions=_parse_extensions(
                os.environ.get("INPUT_EXTRA_EXTENSIONS", "")
            ),
            enable_pr_context=os.environ.get("INPUT_ENABLE_PR_CONTEXT", "true").lower()
            == "true",
            search_related_issues=os.environ.get(
                "INPUT_SEARCH_RELATED_ISSUES", "false"
            ).lower()
            == "true",
            embedding_model=os.environ.get("INPUT_EMBEDDING_MODEL", ""),
        )


def _parse_extensions(raw: str) -> list[str]:
    """Parse comma-separated extensions, ensuring each starts with '.'."""
    exts: list[str] = []
    for ext in raw.split(","):
        ext = ext.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        exts.append(ext)
    return exts
