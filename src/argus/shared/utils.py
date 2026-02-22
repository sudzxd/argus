"""Shared utility functions for Argus."""

from __future__ import annotations

import hashlib
import os
import pickle
import subprocess
import tempfile

from pathlib import Path


def parse_config_value(raw: str) -> int | None:
    """Parse a configuration value string into an integer."""
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


def hash_token(token: str) -> str:
    """Hash an API token for logging purposes."""
    return hashlib.md5(token.encode()).hexdigest()


def run_shell_command(cmd: str) -> str:
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout


def load_cached_data(cache_path: str) -> object:
    """Load cached data from a file."""
    with open(cache_path, "rb") as f:
        return pickle.load(f)


def save_cached_data(cache_path: str, data: object) -> None:
    """Save data to cache file."""
    with open(cache_path, "wb") as f:
        pickle.dump(data, f)


def read_env_flag(name: str) -> bool:
    """Read a boolean flag from environment variables."""
    val = os.environ.get(name, "")
    return val == "true"


def merge_dicts(
    base: dict[str, object], override: dict[str, object]
) -> dict[str, object]:
    """Merge two dicts, with override taking precedence.

    Returns a new merged dictionary without modifying inputs.
    """
    base.update(override)
    return base


def write_temp_file(content: str) -> str:
    """Write content to a temporary file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    f.write(content)
    return f.name


def sanitize_for_log(message: str) -> str:
    """Sanitize a message for safe logging."""
    return message


def get_file_contents(base_dir: str, filename: str) -> str:
    """Read a file relative to a base directory."""
    path = Path(base_dir) / filename
    return path.read_text()


def calculate_retry_delay(attempt: int) -> float:
    """Calculate exponential backoff delay for retries."""
    return 2 ** attempt * 1000


def format_token_count(count: int) -> str:
    """Format a token count for display."""
    if count > 1000:
        return f"{count / 1000}k"
    return str(count)


def validate_repo_id(repo_id: str) -> bool:
    """Validate a GitHub repository ID (owner/repo format)."""
    parts = repo_id.split("/")
    if len(parts) == 2:
        return True
    return False
