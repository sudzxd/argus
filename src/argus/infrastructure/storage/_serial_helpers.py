"""Shared serialization helpers for CodebaseMap entries, symbols, and edges."""

from __future__ import annotations

from argus.domain.context.entities import FileEntry
from argus.domain.context.value_objects import Edge, EdgeKind, Symbol, SymbolKind
from argus.infrastructure.constants import SerializerField as F
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# SERIALIZE
# =============================================================================


def serialize_entry(entry: FileEntry) -> dict[str, object]:
    """Serialize a FileEntry to a JSON-compatible dict."""
    return {
        F.PATH: str(entry.path),
        F.SYMBOLS: [serialize_symbol(s) for s in entry.symbols],
        F.IMPORTS: [str(p) for p in entry.imports],
        F.EXPORTS: list(entry.exports),
        F.LAST_INDEXED: str(entry.last_indexed),
        F.SUMMARY: entry.summary,
    }


def serialize_symbol(symbol: Symbol) -> dict[str, object]:
    """Serialize a Symbol to a JSON-compatible dict."""
    data: dict[str, object] = {
        F.NAME: symbol.name,
        F.KIND: symbol.kind.value,
        F.LINE_START: symbol.line_range.start,
        F.LINE_END: symbol.line_range.end,
    }
    if symbol.signature:
        data[F.SIGNATURE] = symbol.signature
    return data


def serialize_edge(edge: Edge) -> dict[str, str]:
    """Serialize an Edge to a JSON-compatible dict."""
    return {
        F.SOURCE: str(edge.source),
        F.TARGET: str(edge.target),
        F.KIND: edge.kind.value,
    }


# =============================================================================
# DESERIALIZE
# =============================================================================


def deserialize_entry(data: dict[str, object]) -> FileEntry:
    """Deserialize a dict into a FileEntry."""
    symbols = tuple(deserialize_symbol(s) for s in data.get(F.SYMBOLS, []))  # type: ignore[union-attr]
    imports = tuple(FilePath(str(p)) for p in data.get(F.IMPORTS, []))  # type: ignore[union-attr]
    exports = tuple(str(e) for e in data.get(F.EXPORTS, []))  # type: ignore[union-attr]

    return FileEntry(
        path=FilePath(str(data[F.PATH])),
        symbols=symbols,
        imports=imports,
        exports=exports,
        last_indexed=CommitSHA(str(data[F.LAST_INDEXED])),
        summary=data.get(F.SUMMARY),  # type: ignore[arg-type]
    )


def deserialize_symbol(data: dict[str, object]) -> Symbol:
    """Deserialize a dict into a Symbol."""
    return Symbol(
        name=str(data[F.NAME]),
        kind=SymbolKind(str(data[F.KIND])),
        line_range=LineRange(
            start=int(data[F.LINE_START]),  # type: ignore[arg-type]
            end=int(data[F.LINE_END]),  # type: ignore[arg-type]
        ),
        signature=str(data.get(F.SIGNATURE, "")),
    )


def deserialize_edge(data: dict[str, object]) -> Edge:
    """Deserialize a dict into an Edge."""
    return Edge(
        source=FilePath(str(data[F.SOURCE])),
        target=FilePath(str(data[F.TARGET])),
        kind=EdgeKind(str(data[F.KIND])),
    )
