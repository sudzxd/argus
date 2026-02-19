"""Tests for shard serializer — split, assemble, serialize, deserialize."""

from __future__ import annotations

import pytest

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    Edge,
    EdgeKind,
    ShardId,
    Symbol,
    SymbolKind,
)
from argus.infrastructure.storage.shard_serializer import (
    assemble_from_shards,
    deserialize_shard,
    serialize_shard,
    split_into_shards,
)
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def multi_dir_map() -> CodebaseMap:
    """CodebaseMap with files in multiple directories."""
    cbm = CodebaseMap(indexed_at=CommitSHA("abc123"))

    # src/auth/login.py
    cbm.upsert(
        FileEntry(
            path=FilePath("src/auth/login.py"),
            symbols=[
                Symbol(
                    name="login",
                    kind=SymbolKind.FUNCTION,
                    line_range=LineRange(start=1, end=10),
                ),
            ],
            imports=[FilePath("src/db/models.py")],
            exports=["login"],
            last_indexed=CommitSHA("abc123"),
        )
    )

    # src/auth/utils.py
    cbm.upsert(
        FileEntry(
            path=FilePath("src/auth/utils.py"),
            symbols=[],
            imports=[],
            exports=[],
            last_indexed=CommitSHA("abc123"),
        )
    )

    # src/db/models.py
    cbm.upsert(
        FileEntry(
            path=FilePath("src/db/models.py"),
            symbols=[
                Symbol(
                    name="User",
                    kind=SymbolKind.CLASS,
                    line_range=LineRange(start=1, end=20),
                ),
            ],
            imports=[],
            exports=["User"],
            last_indexed=CommitSHA("abc123"),
            summary="Database models.",
        )
    )

    # Internal edge (same shard: src/auth)
    cbm.graph.add_edge(
        Edge(
            source=FilePath("src/auth/login.py"),
            target=FilePath("src/auth/utils.py"),
            kind=EdgeKind.IMPORTS,
        )
    )

    # Cross-shard edge (src/auth → src/db)
    cbm.graph.add_edge(
        Edge(
            source=FilePath("src/auth/login.py"),
            target=FilePath("src/db/models.py"),
            kind=EdgeKind.IMPORTS,
        )
    )

    return cbm


# =============================================================================
# serialize / deserialize shard
# =============================================================================


def test_serialize_shard_returns_json() -> None:
    entry = FileEntry(
        path=FilePath("a.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("sha1"),
    )
    result = serialize_shard([entry], [])
    assert isinstance(result, str)
    assert "a.py" in result


def test_shard_round_trip() -> None:
    entry = FileEntry(
        path=FilePath("src/main.py"),
        symbols=[
            Symbol(
                name="main",
                kind=SymbolKind.FUNCTION,
                line_range=LineRange(start=1, end=5),
                signature="def main()",
            ),
        ],
        imports=[FilePath("src/utils.py")],
        exports=["main"],
        last_indexed=CommitSHA("abc"),
        summary="Entry point.",
    )
    edge = Edge(
        source=FilePath("src/main.py"),
        target=FilePath("src/utils.py"),
        kind=EdgeKind.IMPORTS,
    )

    json_str = serialize_shard([entry], [edge])
    entries, edges = deserialize_shard(json_str)

    assert len(entries) == 1
    assert entries[0].path == FilePath("src/main.py")
    assert entries[0].symbols[0].name == "main"
    assert entries[0].symbols[0].signature == "def main()"
    assert entries[0].summary == "Entry point."

    assert len(edges) == 1
    assert edges[0].source == FilePath("src/main.py")
    assert edges[0].kind == EdgeKind.IMPORTS


def test_deserialize_shard_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid shard JSON"):
        deserialize_shard("not json {{{")


# =============================================================================
# split_into_shards
# =============================================================================


def test_split_creates_correct_shard_count(
    multi_dir_map: CodebaseMap,
) -> None:
    manifest, shard_data = split_into_shards(multi_dir_map)

    # Two directories: src/auth (2 files) and src/db (1 file).
    assert len(manifest.shards) == 2
    assert len(shard_data) == 2
    assert ShardId("src/auth") in manifest.shards
    assert ShardId("src/db") in manifest.shards


def test_split_file_counts_correct(multi_dir_map: CodebaseMap) -> None:
    manifest, _ = split_into_shards(multi_dir_map)

    assert manifest.shards[ShardId("src/auth")].file_count == 2
    assert manifest.shards[ShardId("src/db")].file_count == 1


def test_split_classifies_cross_shard_edges(
    multi_dir_map: CodebaseMap,
) -> None:
    manifest, _ = split_into_shards(multi_dir_map)

    # One cross-shard edge: login.py → models.py.
    assert len(manifest.cross_shard_edges) == 1
    edge = manifest.cross_shard_edges[0]
    assert edge.source_shard == ShardId("src/auth")
    assert edge.target_shard == ShardId("src/db")


def test_split_internal_edges_in_shard_data(
    multi_dir_map: CodebaseMap,
) -> None:
    _, shard_data = split_into_shards(multi_dir_map)

    # src/auth shard should have internal edge: login.py → utils.py.
    entries, edges = deserialize_shard(shard_data[ShardId("src/auth")])
    assert len(entries) == 2
    assert len(edges) == 1
    assert edges[0].source == FilePath("src/auth/login.py")
    assert edges[0].target == FilePath("src/auth/utils.py")


def test_split_indexed_at_preserved(multi_dir_map: CodebaseMap) -> None:
    manifest, _ = split_into_shards(multi_dir_map)
    assert manifest.indexed_at == CommitSHA("abc123")


# =============================================================================
# assemble_from_shards
# =============================================================================


def test_assemble_full_round_trip(multi_dir_map: CodebaseMap) -> None:
    """Split → assemble all shards = original map."""
    manifest, shard_data = split_into_shards(multi_dir_map)
    restored = assemble_from_shards(manifest, shard_data)

    assert len(restored) == len(multi_dir_map)
    assert restored.indexed_at == multi_dir_map.indexed_at

    for path in multi_dir_map.files():
        original = multi_dir_map.get(path)
        roundtripped = restored.get(path)
        assert roundtripped.path == original.path
        assert len(roundtripped.symbols) == len(original.symbols)

    # All edges (internal + cross-shard) should be restored.
    assert restored.graph.edges == multi_dir_map.graph.edges


def test_assemble_partial_only_loads_requested(
    multi_dir_map: CodebaseMap,
) -> None:
    """Loading only one shard gives a partial map."""
    manifest, shard_data = split_into_shards(multi_dir_map)

    # Only load src/auth.
    partial_data = {ShardId("src/auth"): shard_data[ShardId("src/auth")]}
    partial = assemble_from_shards(manifest, partial_data)

    assert len(partial) == 2  # login.py + utils.py
    assert FilePath("src/auth/login.py") in partial
    assert FilePath("src/db/models.py") not in partial


def test_assemble_partial_no_cross_shard_edges(
    multi_dir_map: CodebaseMap,
) -> None:
    """Cross-shard edges are not restored when target shard is missing."""
    manifest, shard_data = split_into_shards(multi_dir_map)

    partial_data = {ShardId("src/auth"): shard_data[ShardId("src/auth")]}
    partial = assemble_from_shards(manifest, partial_data)

    # Only internal edge should be present.
    assert len(partial.graph.edges) == 1
    edge = next(iter(partial.graph.edges))
    assert edge.source == FilePath("src/auth/login.py")
    assert edge.target == FilePath("src/auth/utils.py")


def test_assemble_empty_shard_data() -> None:
    manifest = split_into_shards(CodebaseMap(indexed_at=CommitSHA("empty")))[0]
    result = assemble_from_shards(manifest, {})
    assert len(result) == 0


# =============================================================================
# Edge case: single-file shard
# =============================================================================


def test_split_single_file() -> None:
    cbm = CodebaseMap(indexed_at=CommitSHA("sha1"))
    cbm.upsert(
        FileEntry(
            path=FilePath("main.py"),
            symbols=[],
            imports=[],
            exports=[],
            last_indexed=CommitSHA("sha1"),
        )
    )

    manifest, _shard_data = split_into_shards(cbm)

    assert len(manifest.shards) == 1
    assert ShardId(".") in manifest.shards
    assert manifest.shards[ShardId(".")].file_count == 1
