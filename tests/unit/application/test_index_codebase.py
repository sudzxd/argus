"""Tests for IndexCodebase use case."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from argus.application.dto import IndexCodebaseCommand, IndexCodebaseResult
from argus.application.index_codebase import IndexCodebase
from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_indexing_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_repository() -> MagicMock:
    return MagicMock()


@pytest.fixture
def use_case(
    mock_indexing_service: MagicMock, mock_repository: MagicMock
) -> IndexCodebase:
    return IndexCodebase(
        indexing_service=mock_indexing_service, repository=mock_repository
    )


def _make_file_entry(path: str, sha: str = "abc") -> FileEntry:
    return FileEntry(
        path=FilePath(path),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA(sha),
    )


def _make_codebase_map(sha: str, entries: list[FileEntry] | None = None) -> CodebaseMap:
    cmap = CodebaseMap(indexed_at=CommitSHA(sha))
    for entry in entries or []:
        cmap.upsert(entry)
    return cmap


# =============================================================================
# Full index — no existing map
# =============================================================================


def test_full_index_when_no_existing_map(
    use_case: IndexCodebase,
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
) -> None:
    mock_repository.load.return_value = None
    mock_indexing_service.full_index.return_value = _make_codebase_map(
        "abc123",
        [
            _make_file_entry("main.py", "abc123"),
            _make_file_entry("util.py", "abc123"),
        ],
    )

    cmd = IndexCodebaseCommand(
        repo_id="org/repo",
        commit_sha=CommitSHA("abc123"),
        file_contents={
            FilePath("main.py"): "print('hi')",
            FilePath("util.py"): "def helper(): pass",
        },
    )

    result = use_case.execute(cmd)

    assert isinstance(result, IndexCodebaseResult)
    assert result.files_indexed == 2
    assert result.checkpoint.commit_sha == CommitSHA("abc123")
    mock_indexing_service.full_index.assert_called_once()


# =============================================================================
# Incremental update — existing map
# =============================================================================


def test_incremental_update_when_map_exists(
    use_case: IndexCodebase,
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
) -> None:
    existing_map = _make_codebase_map(
        "old_sha", [_make_file_entry("existing.py", "old_sha")]
    )
    mock_repository.load.return_value = existing_map

    updated_map = _make_codebase_map(
        "new_sha",
        [
            _make_file_entry("existing.py", "old_sha"),
            _make_file_entry("changed.py", "new_sha"),
        ],
    )
    mock_indexing_service.incremental_update.return_value = updated_map

    cmd = IndexCodebaseCommand(
        repo_id="org/repo",
        commit_sha=CommitSHA("new_sha"),
        file_contents={FilePath("changed.py"): "x = 1"},
    )

    result = use_case.execute(cmd)

    assert result.files_indexed == 1
    assert result.checkpoint.commit_sha == CommitSHA("new_sha")
    mock_indexing_service.incremental_update.assert_called_once()
    mock_repository.save.assert_called_once()
