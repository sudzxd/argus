"""Domain services for the Context Engine bounded context."""

from __future__ import annotations

import logging

from dataclasses import dataclass

from argus.domain.context.entities import CodebaseMap
from argus.domain.context.repositories import CodebaseMapRepository, SourceParser
from argus.shared.exceptions import IndexingError
from argus.shared.types import CommitSHA, FilePath

logger = logging.getLogger(__name__)

# =============================================================================
# INDEXING SERVICE
# =============================================================================


@dataclass
class IndexingService:
    """Orchestrates full and incremental codebase indexing.

    Uses a SourceParser to parse files and a CodebaseMapRepository to
    persist results. Enforces domain invariants: graph consistency with
    file entries, and all entries parsed from source.
    """

    parser: SourceParser
    repository: CodebaseMapRepository

    def full_index(
        self,
        repo_id: str,
        commit_sha: CommitSHA,
        file_contents: dict[FilePath, str],
    ) -> CodebaseMap:
        """Build a complete CodebaseMap from scratch.

        Args:
            repo_id: Repository identifier.
            commit_sha: The commit being indexed.
            file_contents: Mapping of file paths to their source content.

        Returns:
            A new CodebaseMap containing all successfully parsed files.
        """
        codebase_map = CodebaseMap(indexed_at=commit_sha)

        for path, content in file_contents.items():
            try:
                entry = self.parser.parse(path, content)
                codebase_map.upsert(entry)
            except IndexingError:
                logger.warning("Skipping unparseable file: %s", path)

        self.repository.save(repo_id, codebase_map)
        return codebase_map

    def incremental_update(
        self,
        codebase_map: CodebaseMap,
        commit_sha: CommitSHA,
        file_contents: dict[FilePath, str],
    ) -> CodebaseMap:
        """Update an existing CodebaseMap with changed files only.

        Unchanged files are preserved. Changed files are reparsed and their
        graph edges are rebuilt. If a file fails to parse, its old entry
        is kept.

        Args:
            codebase_map: The existing map to update.
            commit_sha: The new commit SHA.
            file_contents: Changed files and their new content.

        Returns:
            The updated CodebaseMap.
        """
        codebase_map.indexed_at = commit_sha

        for path, content in file_contents.items():
            try:
                # Clean old edges before reinserting
                codebase_map.graph.remove_file(path)
                entry = self.parser.parse(path, content)
                codebase_map.upsert(entry)
            except IndexingError:
                logger.warning("Failed to reparse %s, keeping old entry", path)

        return codebase_map
