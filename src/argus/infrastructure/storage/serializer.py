"""CodebaseMap JSON serialization."""

from __future__ import annotations

import json

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    DependencyGraph,
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.infrastructure.constants import SerializerField as F
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# SERIALIZE
# =============================================================================


def serialize(codebase_map: CodebaseMap) -> str:
    """Serialize a CodebaseMap to a JSON string."""
    data = {
        F.INDEXED_AT: str(codebase_map.indexed_at),
        F.ENTRIES: [_serialize_entry(e) for e in _iter_entries(codebase_map)],
        F.EDGES: [_serialize_edge(e) for e in codebase_map.graph.edges],
    }
    return json.dumps(data, indent=2)


def _iter_entries(codebase_map: CodebaseMap) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for path in sorted(codebase_map.files()):
        entries.append(codebase_map.get(path))
    return entries


def _serialize_entry(entry: FileEntry) -> dict[str, object]:
    return {
        F.PATH: str(entry.path),
        F.SYMBOLS: [_serialize_symbol(s) for s in entry.symbols],
        F.IMPORTS: [str(p) for p in entry.imports],
        F.EXPORTS: list(entry.exports),
        F.LAST_INDEXED: str(entry.last_indexed),
        F.SUMMARY: entry.summary,
    }


def _serialize_symbol(symbol: Symbol) -> dict[str, object]:
    data: dict[str, object] = {
        F.NAME: symbol.name,
        F.KIND: symbol.kind.value,
        F.LINE_START: symbol.line_range.start,
        F.LINE_END: symbol.line_range.end,
    }
    if symbol.signature:
        data[F.SIGNATURE] = symbol.signature
    return data


def _serialize_edge(edge: Edge) -> dict[str, str]:
    return {
        F.SOURCE: str(edge.source),
        F.TARGET: str(edge.target),
        F.KIND: edge.kind.value,
    }


# =============================================================================
# DESERIALIZE
# =============================================================================


def deserialize(data: str) -> CodebaseMap:
    """Deserialize a JSON string into a CodebaseMap.

    Raises:
        ValueError: If the JSON is malformed or missing fields.
    """
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as e:
        msg = f"invalid JSON: {e}"
        raise ValueError(msg) from e

    codebase_map = CodebaseMap(indexed_at=CommitSHA(raw[F.INDEXED_AT]))

    for entry_data in raw.get(F.ENTRIES, []):
        entry = _deserialize_entry(entry_data)
        codebase_map.upsert(entry)

    graph = DependencyGraph()
    for edge_data in raw.get(F.EDGES, []):
        graph.add_edge(_deserialize_edge(edge_data))
    codebase_map.graph = graph

    return codebase_map


def _deserialize_entry(data: dict[str, object]) -> FileEntry:
    symbols = [_deserialize_symbol(s) for s in data.get(F.SYMBOLS, [])]  # type: ignore[union-attr]
    imports = [FilePath(str(p)) for p in data.get(F.IMPORTS, [])]  # type: ignore[union-attr]
    exports = [str(e) for e in data.get(F.EXPORTS, [])]  # type: ignore[union-attr]

    return FileEntry(
        path=FilePath(str(data[F.PATH])),
        symbols=symbols,
        imports=imports,
        exports=exports,
        last_indexed=CommitSHA(str(data[F.LAST_INDEXED])),
        summary=data.get(F.SUMMARY),  # type: ignore[arg-type]
    )


def _deserialize_symbol(data: dict[str, object]) -> Symbol:
    return Symbol(
        name=str(data[F.NAME]),
        kind=SymbolKind(str(data[F.KIND])),
        line_range=LineRange(
            start=int(data[F.LINE_START]),  # type: ignore[arg-type]
            end=int(data[F.LINE_END]),  # type: ignore[arg-type]
        ),
        signature=str(data.get(F.SIGNATURE, "")),
    )


def _deserialize_edge(data: dict[str, object]) -> Edge:
    return Edge(
        source=FilePath(str(data[F.SOURCE])),
        target=FilePath(str(data[F.TARGET])),
        kind=EdgeKind(str(data[F.KIND])),
    )
