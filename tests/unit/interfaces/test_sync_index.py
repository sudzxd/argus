"""Tests for the incremental sync_index entry point."""

from __future__ import annotations

import json

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.infrastructure.storage.artifact_store import ShardedArtifactStore
from argus.interfaces.sync_index import (
    _extract_after_sha,
    _incremental_update_sharded,
    _is_parseable,
)
from argus.shared.exceptions import ConfigurationError
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# _is_parseable tests
# =============================================================================


def test_is_parseable_python_file() -> None:
    assert _is_parseable("src/main.py", frozenset({".py", ".js"})) is True


def test_is_parseable_unknown_extension() -> None:
    assert _is_parseable("readme.md", frozenset({".py", ".js"})) is False


def test_is_parseable_no_extension() -> None:
    assert _is_parseable("Makefile", frozenset({".py"})) is False


# =============================================================================
# _extract_after_sha tests
# =============================================================================


def test_extract_after_sha_valid(tmp_path: Path) -> None:
    event = {"before": "aaa111", "after": "bbb222"}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    after = _extract_after_sha(str(event_path))
    assert after == "bbb222"


def test_extract_after_sha_missing_field(tmp_path: Path) -> None:
    event = {"ref": "refs/heads/main"}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    with pytest.raises(ConfigurationError, match="after"):
        _extract_after_sha(str(event_path))


def test_extract_after_sha_missing_file() -> None:
    with pytest.raises(ConfigurationError, match="Event file not found"):
        _extract_after_sha("/nonexistent/path/event.json")


def test_extract_after_sha_invalid_json(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json{{{")
    with pytest.raises(ConfigurationError, match="Invalid event JSON"):
        _extract_after_sha(str(bad_file))


# =============================================================================
# _incremental_update_sharded tests
# =============================================================================


def test_incremental_update_sharded_processes_changed_files(
    tmp_path: Path,
) -> None:
    """Changed parseable files are fetched, parsed, and upserted."""
    client = MagicMock()
    client.compare_commits.return_value = [
        "src/auth.py",
        "README.md",  # not parseable
        "src/utils.py",
    ]
    client.get_file_content.return_value = "def hello(): pass\n"

    parser = MagicMock()
    mock_entry = FileEntry(
        path=FilePath("src/auth.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("bbb222"),
    )
    parser.parse.return_value = mock_entry

    store = ShardedArtifactStore(storage_dir=tmp_path)
    codebase_map = CodebaseMap(indexed_at=CommitSHA("aaa111"))

    _changed, orphaned = _incremental_update_sharded(
        client,
        parser,
        store,
        codebase_map,
        "owner/repo",
        "aaa111",
        "bbb222",
    )

    # compare_commits called with before/after
    client.compare_commits.assert_called_once_with("aaa111", "bbb222")

    # Only parseable files fetched (auth.py, utils.py — not README.md)
    assert client.get_file_content.call_count == 2

    # indexed_at updated
    assert codebase_map.indexed_at == CommitSHA("bbb222")

    # Store saved sharded artifacts
    loaded = store.load_full("owner/repo")
    assert loaded is not None

    # No orphans on fresh save (no existing manifest)
    assert orphaned == set()


def test_incremental_update_sharded_no_parseable_changes_skips(
    tmp_path: Path,
) -> None:
    """When no parseable files changed, nothing happens."""
    client = MagicMock()
    client.compare_commits.return_value = ["README.md", "docs/guide.txt"]

    parser = MagicMock()
    store = ShardedArtifactStore(storage_dir=tmp_path)
    codebase_map = CodebaseMap(indexed_at=CommitSHA("aaa111"))

    _changed_files, orphaned = _incremental_update_sharded(
        client,
        parser,
        store,
        codebase_map,
        "owner/repo",
        "aaa111",
        "bbb222",
    )

    client.get_file_content.assert_not_called()
    parser.parse.assert_not_called()
    # indexed_at unchanged
    assert codebase_map.indexed_at == CommitSHA("aaa111")
    assert _changed_files == []
    assert orphaned == set()
