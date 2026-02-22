"""Shared environment variable helpers for interfaces."""

from __future__ import annotations

import os

from argus.shared.exceptions import ConfigurationError


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
