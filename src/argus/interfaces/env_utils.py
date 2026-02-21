"""Shared environment variable helpers and default constants for interfaces."""

from __future__ import annotations

import os

from argus.shared.exceptions import ConfigurationError

# Review mode defaults.
DEFAULT_REVIEW_MODEL = "anthropic:claude-sonnet-4-5-20250929"
DEFAULT_REVIEW_MAX_TOKENS = 128_000

# Index / bootstrap mode defaults.
DEFAULT_INDEX_MODEL = "google-gla:gemini-2.5-flash"
DEFAULT_INDEX_MAX_TOKENS = 1_000_000


def require_env(name: str) -> str:
    """Read a required environment variable or raise.

    Raises:
        ConfigurationError: If the variable is missing or empty.
    """
    value = os.environ.get(name)
    if not value:
        msg = f"Missing required environment variable: {name}"
        raise ConfigurationError(msg)
    return value
