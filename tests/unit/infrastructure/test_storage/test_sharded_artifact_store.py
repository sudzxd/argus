"""Tests for ShardedArtifactStore."""

from __future__ import annotations

from pathlib import Path

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    Edge,
    EdgeKind,
    ShardId,
    Symbol,
    SymbolKind,
)
from argus.infrastructure.storage.artifact_store import (
    FileArtifactStore,
    ShardedArtifactStore,
)
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# Helpers
# =============================================================================


def _build_map() -> CodebaseMap:
    """Build a small multi-directory CodebaseMap."""
    cbm = CodebaseMap(indexed_at=CommitSHA("sha123"))
    cbm.upsert(
        FileEntry(
            path=FilePath("src/main.py"),
            symbols=[
                Symbol(
                    name="main",
                    kind=SymbolKind.FUNCTION,
                    line_range=LineRange(start=1, end=5),
                ),
            ],
            imports=[FilePath("lib/utils.py")],
            exports=["main"],
            last_indexed=CommitSHA("sha123"),
        )
    )
    cbm.upsert(
        FileEntry(
            path=FilePath("lib/utils.py"),
            symbols=[],
            imports=[],
            exports=["helper"],
            last_indexed=CommitSHA("sha123"),
        )
    )
    cbm.graph.add_edge(
        Edge(
            source=FilePath("src/main.py"),
            target=FilePath("lib/utils.py"),
            kind=EdgeKind.IMPORTS,
        )
    )
    return cbm


# =============================================================================
# save_full / load_full round-trip
# =============================================================================


def test_save_full_and_load_full(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    cbm = _build_map()

    store.save_full("org/repo", cbm)
    loaded = store.load_full("org/repo")

    assert loaded is not None
    assert len(loaded) == 2
    assert loaded.indexed_at == CommitSHA("sha123")
    assert FilePath("src/main.py") in loaded
    assert FilePath("lib/utils.py") in loaded


def test_save_full_creates_manifest(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    store.save_full("org/repo", _build_map())

    manifest = store.load_manifest("org/repo")
    assert manifest is not None
    assert len(manifest.shards) == 2


def test_save_full_creates_shard_files(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    store.save_full("org/repo", _build_map())

    shard_files = list(tmp_path.glob("shard_*.json"))
    assert len(shard_files) == 2


# =============================================================================
# load_manifest
# =============================================================================


def test_load_manifest_returns_none_when_missing(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    assert store.load_manifest("org/repo") is None


def test_load_manifest_returns_none_when_corrupt(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "manifest.json").write_text("not json", encoding="utf-8")

    assert store.load_manifest("org/repo") is None


# =============================================================================
# load_shards (selective)
# =============================================================================


def test_load_shards_partial(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    store.save_full("org/repo", _build_map())

    # Load only the src shard.
    partial = store.load_shards("org/repo", {ShardId("src")})
    assert len(partial) == 1
    assert FilePath("src/main.py") in partial
    assert FilePath("lib/utils.py") not in partial


def test_load_shards_missing_shard_skipped(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    store.save_full("org/repo", _build_map())

    # Request a non-existent shard.
    partial = store.load_shards("org/repo", {ShardId("nonexistent")})
    assert len(partial) == 0


# =============================================================================
# load_or_migrate
# =============================================================================


def test_load_or_migrate_sharded(tmp_path: Path) -> None:
    """When sharded artifacts exist, load_or_migrate returns them."""
    store = ShardedArtifactStore(storage_dir=tmp_path)
    store.save_full("org/repo", _build_map())

    result = store.load_or_migrate("org/repo")
    assert result is not None
    assert len(result) == 2


def test_load_or_migrate_legacy(tmp_path: Path) -> None:
    """When only legacy flat format exists, load_or_migrate returns it."""
    legacy = FileArtifactStore(storage_dir=tmp_path)
    cbm = CodebaseMap(indexed_at=CommitSHA("legacy"))
    cbm.upsert(
        FileEntry(
            path=FilePath("old.py"),
            symbols=[],
            imports=[],
            exports=[],
            last_indexed=CommitSHA("legacy"),
        )
    )
    legacy.save("org/repo", cbm)

    store = ShardedArtifactStore(storage_dir=tmp_path)
    result = store.load_or_migrate("org/repo")
    assert result is not None
    assert len(result) == 1
    assert result.indexed_at == CommitSHA("legacy")


def test_load_or_migrate_nothing(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    assert store.load_or_migrate("org/repo") is None


# =============================================================================
# save_full removes legacy artifact
# =============================================================================


def test_save_full_removes_legacy(tmp_path: Path) -> None:
    # Create legacy artifact first.
    legacy = FileArtifactStore(storage_dir=tmp_path)
    legacy.save("org/repo", CodebaseMap(indexed_at=CommitSHA("old")))
    legacy_path = legacy._path_for("org/repo")
    assert legacy_path.exists()

    # Save sharded — should clean up legacy.
    store = ShardedArtifactStore(storage_dir=tmp_path)
    store.save_full("org/repo", _build_map())

    assert not legacy_path.exists()


# =============================================================================
# Empty map
# =============================================================================


def test_save_and_load_empty_map(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    cbm = CodebaseMap(indexed_at=CommitSHA("empty"))

    store.save_full("org/repo", cbm)
    loaded = store.load_full("org/repo")

    assert loaded is not None
    assert len(loaded) == 0
    assert loaded.indexed_at == CommitSHA("empty")


# =============================================================================
# save_incremental orphan cleanup
# =============================================================================


def test_save_incremental_returns_orphaned_blobs(tmp_path: Path) -> None:
    """When a shard's content changes, the old blob name is returned."""
    store = ShardedArtifactStore(storage_dir=tmp_path)
    cbm = _build_map()
    store.save_full("org/repo", cbm)

    # Record old blob names.
    manifest = store.load_manifest("org/repo")
    assert manifest is not None
    old_blob_names = {desc.blob_name for desc in manifest.shards.values()}

    # Modify a file so the shard content changes.
    cbm.upsert(
        FileEntry(
            path=FilePath("src/main.py"),
            symbols=[
                Symbol(
                    name="main_v2",
                    kind=SymbolKind.FUNCTION,
                    line_range=LineRange(start=1, end=10),
                ),
            ],
            imports=[],
            exports=["main_v2"],
            last_indexed=CommitSHA("sha456"),
        )
    )

    orphaned = store.save_incremental(manifest, cbm)

    # At least the src shard should have a new blob name.
    assert len(orphaned) >= 1
    # Orphaned blobs should be from the old set.
    assert orphaned <= old_blob_names
    # Old orphan files should be deleted from disk.
    for blob_name in orphaned:
        assert not (tmp_path / blob_name).exists()


def test_save_incremental_no_orphans_when_unchanged(tmp_path: Path) -> None:
    """When shard content doesn't change, no orphans are returned."""
    store = ShardedArtifactStore(storage_dir=tmp_path)
    cbm = _build_map()
    store.save_full("org/repo", cbm)

    manifest = store.load_manifest("org/repo")
    assert manifest is not None

    # Save same content — no changes.
    orphaned = store.save_incremental(manifest, cbm)

    assert orphaned == set()
