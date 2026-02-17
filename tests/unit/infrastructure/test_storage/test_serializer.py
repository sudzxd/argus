"""Tests for CodebaseMap JSON serialization."""

from __future__ import annotations

import pytest

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.infrastructure.storage.serializer import deserialize, serialize
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def populated_map() -> CodebaseMap:
    cbm = CodebaseMap(indexed_at=CommitSHA("abc123"))
    entry = FileEntry(
        path=FilePath("src/main.py"),
        symbols=[
            Symbol(
                name="main",
                kind=SymbolKind.FUNCTION,
                line_range=LineRange(start=1, end=5),
            ),
        ],
        imports=[FilePath("src/utils.py")],
        exports=["main"],
        last_indexed=CommitSHA("abc123"),
        summary="Entry point.",
    )
    cbm.upsert(entry)
    cbm.graph.add_edge(
        Edge(
            source=FilePath("src/main.py"),
            target=FilePath("src/utils.py"),
            kind=EdgeKind.IMPORTS,
        )
    )
    return cbm


# =============================================================================
# Tests
# =============================================================================


def test_serialize_returns_json_string(populated_map: CodebaseMap) -> None:
    result = serialize(populated_map)
    assert isinstance(result, str)
    assert "abc123" in result
    assert "src/main.py" in result


def test_round_trip_preserves_entries(populated_map: CodebaseMap) -> None:
    json_str = serialize(populated_map)
    restored = deserialize(json_str)

    assert len(restored) == len(populated_map)
    assert restored.indexed_at == populated_map.indexed_at

    original = populated_map.get(FilePath("src/main.py"))
    roundtripped = restored.get(FilePath("src/main.py"))

    assert roundtripped.path == original.path
    assert roundtripped.last_indexed == original.last_indexed
    assert roundtripped.summary == original.summary
    assert len(roundtripped.symbols) == len(original.symbols)
    assert roundtripped.symbols[0].name == original.symbols[0].name
    assert roundtripped.symbols[0].kind == original.symbols[0].kind
    assert roundtripped.imports == original.imports
    assert roundtripped.exports == original.exports


def test_round_trip_preserves_edges(populated_map: CodebaseMap) -> None:
    json_str = serialize(populated_map)
    restored = deserialize(json_str)

    original_edges = populated_map.graph.edges
    restored_edges = restored.graph.edges

    assert len(restored_edges) == len(original_edges)
    assert restored_edges == original_edges


def test_deserialize_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        deserialize("not valid json {{{")


def test_serialize_empty_map() -> None:
    cbm = CodebaseMap(indexed_at=CommitSHA("empty"))
    json_str = serialize(cbm)
    restored = deserialize(json_str)

    assert len(restored) == 0
    assert restored.indexed_at == CommitSHA("empty")
