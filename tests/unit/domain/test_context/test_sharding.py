"""Tests for sharding value objects and ShardedManifest."""

from __future__ import annotations

import pytest

from argus.domain.context.value_objects import (
    CrossShardEdge,
    EdgeKind,
    ShardDescriptor,
    ShardedManifest,
    ShardId,
    shard_id_for,
)
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# shard_id_for
# =============================================================================


def test_shard_id_for_simple_path() -> None:
    assert shard_id_for(FilePath("src/main.py")) == ShardId("src")


def test_shard_id_for_nested_path() -> None:
    result = shard_id_for(FilePath("src/auth/login.py"))
    assert result == ShardId("src/auth")


def test_shard_id_for_root_file() -> None:
    assert shard_id_for(FilePath("setup.py")) == ShardId(".")


# =============================================================================
# ShardDescriptor
# =============================================================================


def test_shard_descriptor_frozen() -> None:
    desc = ShardDescriptor(
        directory=ShardId("src"),
        file_count=5,
        content_hash="abc123",
        blob_name="shard_abc123.json",
    )
    with pytest.raises(AttributeError):
        desc.file_count = 10  # type: ignore[misc]


# =============================================================================
# CrossShardEdge
# =============================================================================


def test_cross_shard_edge_frozen() -> None:
    edge = CrossShardEdge(
        source_shard=ShardId("src"),
        target_shard=ShardId("lib"),
        source_file=FilePath("src/main.py"),
        target_file=FilePath("lib/utils.py"),
        kind=EdgeKind.IMPORTS,
    )
    with pytest.raises(AttributeError):
        edge.kind = EdgeKind.CALLS  # type: ignore[misc]


# =============================================================================
# ShardedManifest
# =============================================================================


@pytest.fixture
def manifest_with_edges() -> ShardedManifest:
    """Manifest with 3 shards and cross-shard edges."""
    m = ShardedManifest(indexed_at=CommitSHA("sha1"))
    m.shards = {
        ShardId("src/auth"): ShardDescriptor(
            directory=ShardId("src/auth"),
            file_count=2,
            content_hash="aaa",
            blob_name="shard_aaa.json",
        ),
        ShardId("src/db"): ShardDescriptor(
            directory=ShardId("src/db"),
            file_count=1,
            content_hash="bbb",
            blob_name="shard_bbb.json",
        ),
        ShardId("src/api"): ShardDescriptor(
            directory=ShardId("src/api"),
            file_count=3,
            content_hash="ccc",
            blob_name="shard_ccc.json",
        ),
    }
    m.cross_shard_edges = [
        CrossShardEdge(
            source_shard=ShardId("src/auth"),
            target_shard=ShardId("src/db"),
            source_file=FilePath("src/auth/login.py"),
            target_file=FilePath("src/db/models.py"),
            kind=EdgeKind.IMPORTS,
        ),
        CrossShardEdge(
            source_shard=ShardId("src/api"),
            target_shard=ShardId("src/auth"),
            source_file=FilePath("src/api/routes.py"),
            target_file=FilePath("src/auth/login.py"),
            kind=EdgeKind.CALLS,
        ),
    ]
    return m


def test_shards_for_files_maps_to_parent_dirs() -> None:
    m = ShardedManifest(indexed_at=CommitSHA("sha1"))
    files = [FilePath("src/auth/login.py"), FilePath("src/auth/utils.py")]
    result = m.shards_for_files(files)
    assert result == {ShardId("src/auth")}


def test_shards_for_files_multiple_dirs() -> None:
    m = ShardedManifest(indexed_at=CommitSHA("sha1"))
    files = [FilePath("src/auth/login.py"), FilePath("src/db/models.py")]
    result = m.shards_for_files(files)
    assert result == {ShardId("src/auth"), ShardId("src/db")}


def test_adjacent_shards_1hop(
    manifest_with_edges: ShardedManifest,
) -> None:
    # Starting from src/auth, 1-hop neighbors are src/db and src/api.
    result = manifest_with_edges.adjacent_shards(
        {ShardId("src/auth")},
        hops=1,
    )
    assert result == {ShardId("src/db"), ShardId("src/api")}


def test_adjacent_shards_no_edges() -> None:
    m = ShardedManifest(indexed_at=CommitSHA("sha1"))
    result = m.adjacent_shards({ShardId("src")}, hops=1)
    assert result == set()


def test_adjacent_shards_excludes_start(
    manifest_with_edges: ShardedManifest,
) -> None:
    """Adjacent shards should not include the starting shards."""
    result = manifest_with_edges.adjacent_shards(
        {ShardId("src/auth")},
        hops=1,
    )
    assert ShardId("src/auth") not in result


def test_dirty_shards_returns_affected() -> None:
    m = ShardedManifest(indexed_at=CommitSHA("sha1"))
    changed = [
        FilePath("src/auth/login.py"),
        FilePath("src/db/models.py"),
    ]
    result = m.dirty_shards(changed)
    assert result == {ShardId("src/auth"), ShardId("src/db")}


# =============================================================================
# Manifest serialization round-trip
# =============================================================================


def test_manifest_round_trip(manifest_with_edges: ShardedManifest) -> None:
    json_str = manifest_with_edges.to_json()
    restored = ShardedManifest.from_json(json_str)

    assert restored.indexed_at == manifest_with_edges.indexed_at
    assert len(restored.shards) == len(manifest_with_edges.shards)
    assert len(restored.cross_shard_edges) == len(manifest_with_edges.cross_shard_edges)

    for sid, desc in manifest_with_edges.shards.items():
        assert restored.shards[sid].file_count == desc.file_count
        assert restored.shards[sid].content_hash == desc.content_hash
        assert restored.shards[sid].blob_name == desc.blob_name


def test_manifest_round_trip_empty() -> None:
    m = ShardedManifest(indexed_at=CommitSHA("empty"))
    restored = ShardedManifest.from_json(m.to_json())
    assert restored.indexed_at == CommitSHA("empty")
    assert len(restored.shards) == 0
    assert len(restored.cross_shard_edges) == 0
