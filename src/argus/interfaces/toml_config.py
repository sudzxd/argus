"""TOML-based configuration loader.

Reads ``[tool.argus]`` from ``pyproject.toml`` and produces a typed
``ArgusConfig`` dataclass.  Missing file or missing section → all defaults
apply (supports non-Python repos).
"""

from __future__ import annotations

import logging
import tomllib

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from argus.shared.exceptions import ConfigurationError
from argus.shared.types import ReviewDepth

logger = logging.getLogger(__name__)

# ── defaults ────────────────────────────────────────────────────────────
_REVIEW_DEFAULTS: dict[str, Any] = {
    "model": "anthropic:claude-sonnet-4-5-20250929",
    "max_tokens": 128_000,
}

_INDEX_DEFAULTS: dict[str, Any] = {
    "model": "google-gla:gemini-2.5-flash",
    "max_tokens": 1_000_000,
}

_COMMON_DEFAULTS: dict[str, Any] = {
    "temperature": 0.0,
    "confidence_threshold": 0.7,
    "ignored_paths": [],
    "storage_dir": ".argus-artifacts",
    "enable_agentic": False,
    "review_depth": "standard",
    "extra_extensions": [],
    "enable_pr_context": True,
    "search_related_issues": False,
    "embedding_model": "",
    "analyze_patterns": False,
}

_ALL_KNOWN_KEYS = {
    "model",
    "max_tokens",
    "temperature",
    "confidence_threshold",
    "ignored_paths",
    "storage_dir",
    "enable_agentic",
    "review_depth",
    "extra_extensions",
    "enable_pr_context",
    "search_related_issues",
    "embedding_model",
    "analyze_patterns",
    "index",
}


@dataclass(frozen=True)
class ArgusConfig:
    """Typed configuration produced by the TOML loader."""

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
    analyze_patterns: bool = False


def load_argus_config(
    mode: str,
    project_root: Path | None = None,
) -> ArgusConfig:
    """Load Argus configuration from ``pyproject.toml``.

    Merge order (later wins):
        common defaults → mode defaults → ``[tool.argus]`` → ``[tool.argus.index]``
        (index subsection applied only when *mode* is ``"index"`` or ``"bootstrap"``).

    Args:
        mode: Operating mode (``"review"``, ``"index"``, or ``"bootstrap"``).
        project_root: Directory containing ``pyproject.toml``.
            Defaults to ``Path.cwd()``.

    Returns:
        A frozen ``ArgusConfig`` dataclass.

    Raises:
        ConfigurationError: On TOML parse errors or invalid values.
    """
    if project_root is None:
        project_root = Path.cwd()

    toml_path = project_root / "pyproject.toml"

    # 1. Start with common + mode defaults.
    is_index_mode = mode in ("index", "bootstrap")
    mode_defaults = _INDEX_DEFAULTS if is_index_mode else _REVIEW_DEFAULTS
    merged: dict[str, Any] = {**_COMMON_DEFAULTS, **mode_defaults}

    # 2. Read TOML and overlay.
    tool_section = _read_tool_section(toml_path)
    if tool_section is not None:
        _warn_unknown_keys(tool_section)

        # Extract index subsection before merging top-level keys.
        index_sub: dict[str, Any] = {}
        raw_index: Any = tool_section.get("index")
        if isinstance(raw_index, dict):
            index_sub = cast(dict[str, Any], raw_index)

        # Merge top-level (excludes nested "index" table).
        for key, value in tool_section.items():
            if key == "index":
                continue
            merged[key] = value

        # Merge index subsection only in index/bootstrap mode.
        if is_index_mode:
            for key, value in index_sub.items():
                merged[key] = value

    # 3. Post-process and validate.
    merged["extra_extensions"] = _normalize_extensions(
        merged.get("extra_extensions", []),
    )
    merged["review_depth"] = _validate_review_depth(merged.get("review_depth"))
    _validate_ranges(merged)

    return ArgusConfig(
        model=str(merged["model"]),
        max_tokens=int(merged["max_tokens"]),
        temperature=float(merged["temperature"]),
        confidence_threshold=float(merged["confidence_threshold"]),
        ignored_paths=list(merged["ignored_paths"]),
        storage_dir=str(merged["storage_dir"]),
        enable_agentic=bool(merged["enable_agentic"]),
        review_depth=merged["review_depth"],
        extra_extensions=list(merged["extra_extensions"]),
        enable_pr_context=bool(merged["enable_pr_context"]),
        search_related_issues=bool(merged["search_related_issues"]),
        embedding_model=str(merged["embedding_model"]),
        analyze_patterns=bool(merged["analyze_patterns"]),
    )


# ── internal helpers ────────────────────────────────────────────────────


def _read_tool_section(toml_path: Path) -> dict[str, Any] | None:
    """Read ``[tool.argus]`` from *toml_path*, or ``None`` if absent."""
    if not toml_path.is_file():
        return None
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        msg = f"Failed to parse {toml_path}: {exc}"
        raise ConfigurationError(msg) from exc
    tool: dict[str, Any] | None = data.get("tool")
    if not isinstance(tool, dict):
        return None
    argus: dict[str, Any] | None = tool.get("argus")
    if not isinstance(argus, dict):
        return None
    return argus


def _warn_unknown_keys(section: dict[str, Any]) -> None:
    """Log a warning for any keys not in the known set."""
    for top_key in section:
        if top_key not in _ALL_KNOWN_KEYS:
            logger.warning("Unknown key in [tool.argus]: %r", top_key)
    index_sub: Any = section.get("index")
    if isinstance(index_sub, dict):
        sub_dict = cast(dict[str, Any], index_sub)
        for sub_key in sub_dict:
            if sub_key not in _ALL_KNOWN_KEYS:
                logger.warning("Unknown key in [tool.argus.index]: %r", sub_key)


def _normalize_extensions(raw: Any) -> list[str]:
    """Ensure every extension starts with ``'.'``."""
    if not isinstance(raw, list):
        return []
    items = cast(list[str], raw)
    result: list[str] = []
    for item in items:
        ext = item.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        result.append(ext)
    return result


def _validate_review_depth(raw: Any) -> ReviewDepth:
    """Convert a string to ``ReviewDepth`` or raise."""
    try:
        return ReviewDepth(str(raw))
    except ValueError:
        valid = ", ".join(d.value for d in ReviewDepth)
        msg = f"Invalid review_depth {raw!r} (valid: {valid})"
        raise ConfigurationError(msg) from None


def _validate_ranges(merged: dict[str, Any]) -> None:
    """Validate numeric ranges."""
    temp = float(merged.get("temperature", 0.0))
    if not 0.0 <= temp <= 2.0:
        msg = f"temperature must be between 0.0 and 2.0, got {temp}"
        raise ConfigurationError(msg)

    threshold = float(merged.get("confidence_threshold", 0.7))
    if not 0.0 <= threshold <= 1.0:
        msg = f"confidence_threshold must be between 0.0 and 1.0, got {threshold}"
        raise ConfigurationError(msg)
