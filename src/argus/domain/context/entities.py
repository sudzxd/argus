"""Entities for the Context Engine bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.domain.context.value_objects import DependencyGraph, Symbol
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# ENTITIES
# =============================================================================


@dataclass(frozen=True)
class FileEntry:
    """A single source file's parsed representation."""

    path: FilePath
    symbols: list[Symbol]
    imports: list[FilePath]
    exports: list[str]
    last_indexed: CommitSHA
    summary: str | None = None


@dataclass
class CodebaseMap:
    """Aggregate root — the complete semantic map of a repository.

    Not frozen: as an aggregate root this entity manages mutable internal
    state (entries and graph edges). Value objects within it remain frozen.
    """

    indexed_at: CommitSHA
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    _entries: dict[FilePath, FileEntry] = field(
        default_factory=dict[FilePath, FileEntry],
    )

    def upsert(self, entry: FileEntry) -> None:
        """Add or replace a file entry."""
        self._entries[entry.path] = entry

    def get(self, path: FilePath) -> FileEntry:
        """Get a file entry by path.

        Raises:
            KeyError: If the path is not in the map.
        """
        return self._entries[path]

    def remove(self, path: FilePath) -> None:
        """Remove a file entry and its graph edges.

        Raises:
            KeyError: If the path is not in the map.
        """
        if path not in self._entries:
            raise KeyError(path)
        del self._entries[path]
        self.graph.remove_file(path)

    def files(self) -> set[FilePath]:
        """All file paths in the map."""
        return set(self._entries.keys())

    def __contains__(self, path: FilePath) -> bool:
        return path in self._entries

    def __len__(self) -> int:
        return len(self._entries)
