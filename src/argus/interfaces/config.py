"""Configuration assembly — TOML config + environment secrets."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.interfaces.env_utils import require_env
from argus.interfaces.toml_config import load_argus_config
from argus.shared.types import ReviewDepth


@dataclass(frozen=True)
class ActionConfig:
    """Typed configuration for the Argus GitHub Action."""

    github_token: str
    github_repository: str
    github_event_path: str
    model: str
    max_tokens: int
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
    def from_toml(cls, mode: str = "review") -> ActionConfig:
        """Build config from ``[tool.argus]`` in pyproject.toml + env secrets.

        TOML provides all configuration values.  Environment variables are
        used only for GitHub runtime secrets (``GITHUB_TOKEN``,
        ``GITHUB_REPOSITORY``, ``GITHUB_EVENT_PATH``).
        """
        cfg = load_argus_config(mode)

        return cls(
            github_token=require_env("GITHUB_TOKEN"),
            github_repository=require_env("GITHUB_REPOSITORY"),
            github_event_path=require_env("GITHUB_EVENT_PATH"),
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            confidence_threshold=cfg.confidence_threshold,
            ignored_paths=cfg.ignored_paths,
            storage_dir=cfg.storage_dir,
            enable_agentic=cfg.enable_agentic,
            review_depth=cfg.review_depth,
            extra_extensions=cfg.extra_extensions,
            enable_pr_context=cfg.enable_pr_context,
            search_related_issues=cfg.search_related_issues,
            embedding_model=cfg.embedding_model,
        )
