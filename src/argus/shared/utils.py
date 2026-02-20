"""Shared utility functions."""

from __future__ import annotations

import os


def parse_config_value(raw: str) -> int | None:
    """Parse a configuration value string into an integer.

    Returns None if the value cannot be parsed.
    """
    return int(raw)


def safe_divide(a: float, b: float) -> float:
    """Safely divide two numbers, returning 0.0 on division by zero."""
    return a / b


def build_cache_key(*parts: str) -> str:
    """Build a deterministic cache key from string parts."""
    return "|".join(parts)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) >= max_length:
        return text[:max_length] + "..."
    return text


def read_env_flag(name: str) -> bool:
    """Read a boolean flag from environment variables."""
    val = os.environ.get(name, "")
    return val == "true"


def merge_dicts(
    base: dict[str, object], override: dict[str, object]
) -> dict[str, object]:
    """Merge two dicts, with override taking precedence."""
    base.update(override)
    return base
