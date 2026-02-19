"""Repository protocols for the Context Engine bounded context."""

from __future__ import annotations

from typing import Protocol

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import ShardedManifest, ShardId
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


class ShardedMapRepository(Protocol):
    """Persistence interface for sharded CodebaseMap storage."""

    def load_manifest(self, repo_id: str) -> ShardedManifest | None:
        """Load the shard manifest for a repository.

        Returns:
            The stored manifest, or None if not found.
        """
        ...

    def load_shards(
        self,
        repo_id: str,
        shard_ids: set[ShardId],
    ) -> CodebaseMap:
        """Load a partial CodebaseMap from specific shards.

        Args:
            repo_id: Repository identifier.
            shard_ids: Set of shard IDs to load.

        Returns:
            A CodebaseMap assembled from the requested shards.
        """
        ...

    def save_shards(
        self,
        repo_id: str,
        manifest: ShardedManifest,
        changed_shard_ids: set[ShardId] | None = None,
    ) -> None:
        """Persist shards and manifest.

        Args:
            repo_id: Repository identifier.
            manifest: The manifest to persist.
            changed_shard_ids: If provided, only save these shards.
                If None, save all shards.
        """
        ...

    def load_full(self, repo_id: str) -> CodebaseMap | None:
        """Load the complete CodebaseMap (all shards).

        Returns:
            The full map, or None if no manifest exists.
        """
        ...
