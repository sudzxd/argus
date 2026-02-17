"""Repository protocols for the Context Engine bounded context."""

from __future__ import annotations

from typing import Protocol

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.shared.types import FilePath

# =============================================================================
# PROTOCOLS
# =============================================================================


class CodebaseMapRepository(Protocol):
    """Persistence interface for CodebaseMap."""

    def load(self, repo_id: str) -> CodebaseMap | None:
        """Load the codebase map for a repository.

        Args:
            repo_id: Repository identifier (e.g. "org/repo").

        Returns:
            The stored codebase map, or None if no map exists.
        """
        ...

    def save(self, repo_id: str, codebase_map: CodebaseMap) -> None:
        """Persist the codebase map for a repository.

        Args:
            repo_id: Repository identifier.
            codebase_map: The map to persist.
        """
        ...


class SourceParser(Protocol):
    """Interface for parsing source files into structured symbols."""

    def parse(self, path: FilePath, content: str) -> FileEntry:
        """Parse a source file and return its structured representation.

        Args:
            path: Path to the file within the repository.
            content: Raw source code content.

        Returns:
            Parsed file entry with symbols, imports, and exports.

        Raises:
            IndexingError: If the file cannot be parsed.
        """
        ...

    def supported_languages(self) -> frozenset[str]:
        """Return the set of language names this parser supports."""
        ...
