"""Tests for _fetch_files_parallel in action.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from argus.interfaces.action import _fetch_files_parallel
from argus.shared.exceptions import PublishError
from argus.shared.types import FilePath


def _make_client(
    file_map: dict[str, str],
    error_paths: set[str] | None = None,
) -> MagicMock:
    """Build a mock client that returns file contents or raises."""
    error_paths = error_paths or set()

    def get_file_content(path: FilePath, *, ref: str) -> str:
        if str(path) in error_paths:
            raise PublishError(f"Not found: {path}")
        return file_map[str(path)]

    client = MagicMock()
    client.get_file_content = MagicMock(side_effect=get_file_content)
    return client


def test_fetch_files_parallel_returns_contents() -> None:
    client = _make_client({"a.py": "code_a", "b.py": "code_b"})
    paths = [FilePath("a.py"), FilePath("b.py")]

    result = _fetch_files_parallel(client, paths, ref="abc123")

    assert result == {FilePath("a.py"): "code_a", FilePath("b.py"): "code_b"}


def test_fetch_files_parallel_handles_errors_gracefully() -> None:
    client = _make_client(
        {"a.py": "code_a", "b.py": "code_b"},
        error_paths={"b.py"},
    )
    paths = [FilePath("a.py"), FilePath("b.py")]

    result = _fetch_files_parallel(client, paths, ref="abc123")

    assert FilePath("a.py") in result
    assert FilePath("b.py") not in result


def test_fetch_files_parallel_empty_paths_returns_empty_dict() -> None:
    client = MagicMock()

    result = _fetch_files_parallel(client, [], ref="abc123")

    assert result == {}
    client.get_file_content.assert_not_called()
