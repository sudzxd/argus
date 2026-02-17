"""Tests for file-based artifact store."""

from __future__ import annotations

from pathlib import Path

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.infrastructure.storage.artifact_store import FileArtifactStore
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# Tests
# =============================================================================


def test_load_returns_none_when_no_artifact(tmp_path: Path) -> None:
    store = FileArtifactStore(storage_dir=tmp_path)
    assert store.load("org/repo") is None


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = FileArtifactStore(storage_dir=tmp_path)
    cbm = CodebaseMap(indexed_at=CommitSHA("sha1"))
    cbm.upsert(
        FileEntry(
            path=FilePath("a.py"),
            symbols=[],
            imports=[],
            exports=[],
            last_indexed=CommitSHA("sha1"),
        )
    )

    store.save("org/repo", cbm)
    loaded = store.load("org/repo")

    assert loaded is not None
    assert len(loaded) == 1
    assert loaded.indexed_at == CommitSHA("sha1")


def test_save_creates_storage_dir(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "dir"
    store = FileArtifactStore(storage_dir=nested)

    store.save("org/repo", CodebaseMap(indexed_at=CommitSHA("sha1")))

    assert nested.exists()
    assert store.load("org/repo") is not None


def test_load_corrupt_file_returns_none(tmp_path: Path) -> None:
    store = FileArtifactStore(storage_dir=tmp_path)

    # Save valid first to get the file path
    store.save("org/repo", CodebaseMap(indexed_at=CommitSHA("sha1")))
    # Corrupt the file
    artifact_path = store._path_for("org/repo")
    artifact_path.write_text("not valid json", encoding="utf-8")

    assert store.load("org/repo") is None


def test_different_repos_have_different_files(tmp_path: Path) -> None:
    store = FileArtifactStore(storage_dir=tmp_path)

    store.save("org/repo-a", CodebaseMap(indexed_at=CommitSHA("a")))
    store.save("org/repo-b", CodebaseMap(indexed_at=CommitSHA("b")))

    loaded_a = store.load("org/repo-a")
    loaded_b = store.load("org/repo-b")

    assert loaded_a is not None
    assert loaded_b is not None
    assert loaded_a.indexed_at == CommitSHA("a")
    assert loaded_b.indexed_at == CommitSHA("b")
