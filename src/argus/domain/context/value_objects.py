"""Value objects for the Context Engine bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# ENUMS
# =============================================================================


class SymbolKind(StrEnum):
    """Kind of code symbol extracted from AST."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"


class EdgeKind(StrEnum):
    """Kind of relationship between files."""

    IMPORTS = "imports"
    CALLS = "calls"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"


# =============================================================================
# VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class Symbol:
    """A code symbol extracted from a source file."""

    name: str
    kind: SymbolKind
    line_range: LineRange


@dataclass(frozen=True)
class Edge:
    """A directed relationship between two files."""

    source: FilePath
    target: FilePath
    kind: EdgeKind


@dataclass(frozen=True)
class Checkpoint:
    """An immutable snapshot reference for a CodebaseMap version."""

    commit_sha: CommitSHA
    version: str


# =============================================================================
# DEPENDENCY GRAPH
# =============================================================================


@dataclass
class DependencyGraph:
    """Directed graph of file-level relationships."""

    _edges: set[Edge] = field(default_factory=set[Edge])

    @property
    def edges(self) -> frozenset[Edge]:
        """All edges in the graph."""
        return frozenset(self._edges)

    def add_edge(self, edge: Edge) -> None:
        """Add a relationship to the graph."""
        self._edges.add(edge)

    def dependents_of(self, path: FilePath) -> set[FilePath]:
        """Files that depend on the given path (incoming edges)."""
        return {e.source for e in self._edges if e.target == path}

    def dependencies_of(self, path: FilePath) -> set[FilePath]:
        """Files that the given path depends on (outgoing edges)."""
        return {e.target for e in self._edges if e.source == path}

    def remove_file(self, path: FilePath) -> None:
        """Remove all edges involving the given file."""
        self._edges = {e for e in self._edges if e.source != path and e.target != path}

    def files(self) -> set[FilePath]:
        """All files referenced in the graph."""
        result: set[FilePath] = set()
        for e in self._edges:
            result.add(e.source)
            result.add(e.target)
        return result
