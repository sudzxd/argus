"""Tests for Git branch-based artifact storage."""

from __future__ import annotations

import base64

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from argus.infrastructure.storage.git_branch_store import (
    GitBranchSync,
    SelectiveGitBranchSync,
)


@pytest.fixture
def client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def sync(client: MagicMock, tmp_path: Path) -> GitBranchSync:
    return GitBranchSync(client=client, branch="argus-data", storage_dir=tmp_path)


# =============================================================================
# Pull tests
# =============================================================================


def test_pull_no_branch_returns_zero(sync: GitBranchSync, client: MagicMock) -> None:
    """When the branch doesn't exist, pull downloads nothing."""
    client.get_ref_sha.return_value = None

    count = sync.pull()

    assert count == 0
    client.get_commit_tree_sha.assert_not_called()


def test_pull_downloads_artifacts(
    sync: GitBranchSync, client: MagicMock, tmp_path: Path
) -> None:
    """Pull fetches blobs and writes them to storage_dir."""
    client.get_ref_sha.return_value = "abc123"
    client.get_commit_tree_sha.return_value = "tree456"
    client.get_tree_entries_flat.return_value = [
        {"type": "blob", "path": "codebase_map.json", "sha": "blob1"},
        {"type": "blob", "path": "memory.json", "sha": "blob2"},
        {"type": "blob", "path": "README.md", "sha": "blob3"},  # non-JSON, skipped
        {"type": "tree", "path": "subdir", "sha": "tree9"},  # tree, skipped
    ]
    client.get_blob_content.side_effect = [
        b'{"indexed_at": "sha1"}',
        b'{"version": 1}',
    ]

    count = sync.pull()

    assert count == 2
    assert (tmp_path / "codebase_map.json").read_bytes() == b'{"indexed_at": "sha1"}'
    assert (tmp_path / "memory.json").read_bytes() == b'{"version": 1}'
    assert not (tmp_path / "README.md").exists()


# =============================================================================
# Push tests
# =============================================================================


def test_push_creates_orphan_when_no_branch(
    sync: GitBranchSync, client: MagicMock, tmp_path: Path
) -> None:
    """When the branch doesn't exist, push creates an orphan commit."""
    (tmp_path / "map.json").write_text('{"data": 1}')
    client.get_ref_sha.return_value = None
    client.create_blob.return_value = "blob_sha"
    client.create_tree.return_value = "tree_sha"
    client.create_commit.return_value = "commit_sha"

    sync.push()

    # Verify orphan commit (no parents).
    client.create_commit.assert_called_once_with(
        message="chore: update argus artifacts (1 files)",
        tree_sha="tree_sha",
        parents=[],
    )
    client.create_ref.assert_called_once_with("refs/heads/argus-data", "commit_sha")
    client.update_ref.assert_not_called()


def test_push_updates_existing_branch(
    sync: GitBranchSync, client: MagicMock, tmp_path: Path
) -> None:
    """When branch exists, push creates a commit with the existing ref as parent."""
    (tmp_path / "map.json").write_text('{"data": 1}')
    client.get_ref_sha.return_value = "existing_sha"
    client.create_blob.return_value = "blob_sha"
    client.create_tree.return_value = "tree_sha"
    client.create_commit.return_value = "commit_sha"

    sync.push()

    client.create_commit.assert_called_once_with(
        message="chore: update argus artifacts (1 files)",
        tree_sha="tree_sha",
        parents=["existing_sha"],
    )
    client.update_ref.assert_called_once_with("heads/argus-data", "commit_sha")
    client.create_ref.assert_not_called()


def test_push_empty_dir_skips(sync: GitBranchSync, client: MagicMock) -> None:
    """When storage_dir has no JSON files, push does nothing."""
    sync.push()

    client.create_blob.assert_not_called()
    client.create_tree.assert_not_called()
    client.create_commit.assert_not_called()


def test_push_creates_blob_with_base64_content(
    sync: GitBranchSync, client: MagicMock, tmp_path: Path
) -> None:
    """Verify blobs are created with base64-encoded content."""
    content = b'{"key": "value"}'
    (tmp_path / "test.json").write_bytes(content)
    expected_b64 = base64.b64encode(content).decode()

    client.get_ref_sha.return_value = None
    client.create_blob.return_value = "blob_sha"
    client.create_tree.return_value = "tree_sha"
    client.create_commit.return_value = "commit_sha"

    sync.push()

    client.create_blob.assert_called_once_with(expected_b64)


def test_push_multiple_files_sorted(
    sync: GitBranchSync, client: MagicMock, tmp_path: Path
) -> None:
    """Push uploads all JSON files in sorted order."""
    (tmp_path / "b_map.json").write_text("{}")
    (tmp_path / "a_memory.json").write_text("{}")
    (tmp_path / "not_json.txt").write_text("skip me")

    client.get_ref_sha.return_value = None
    client.create_blob.side_effect = ["blob_a", "blob_b"]
    client.create_tree.return_value = "tree_sha"
    client.create_commit.return_value = "commit_sha"

    sync.push()

    # Two JSON files, sorted: a_memory.json before b_map.json.
    assert client.create_blob.call_count == 2
    tree_entries = client.create_tree.call_args[0][0]
    assert tree_entries[0]["path"] == "a_memory.json"
    assert tree_entries[1]["path"] == "b_map.json"


# =============================================================================
# SelectiveGitBranchSync push tests
# =============================================================================


@pytest.fixture
def selective_sync(client: MagicMock, tmp_path: Path) -> SelectiveGitBranchSync:
    return SelectiveGitBranchSync(
        client=client, branch="argus-data", storage_dir=tmp_path
    )


def test_selective_push_delete_blobs_uses_null_sha(
    selective_sync: SelectiveGitBranchSync, client: MagicMock, tmp_path: Path
) -> None:
    """Orphan blob deletion entries use sha=None (JSON null), not a zero hash."""
    (tmp_path / "manifest.json").write_text("{}")
    client.get_ref_sha.return_value = "existing_sha"
    client.get_commit_tree_sha.return_value = "base_tree_sha"
    client.create_blob.return_value = "blob_sha"
    client.create_tree.return_value = "tree_sha"
    client.create_commit.return_value = "commit_sha"

    selective_sync.push(delete_blobs={"shard_old.json"})

    tree_entries = client.create_tree.call_args[0][0]
    delete_entries = [e for e in tree_entries if e["sha"] is None]
    assert len(delete_entries) == 1
    assert delete_entries[0]["path"] == "shard_old.json"
    assert delete_entries[0]["sha"] is None
