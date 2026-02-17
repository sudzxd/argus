"""Index Codebase use case."""

from __future__ import annotations

from dataclasses import dataclass

from argus.application.dto import IndexCodebaseCommand, IndexCodebaseResult
from argus.domain.context.repositories import CodebaseMapRepository
from argus.domain.context.services import IndexingService
from argus.domain.context.value_objects import Checkpoint

# =============================================================================
# USE CASE
# =============================================================================


@dataclass
class IndexCodebase:
    """Load or create a CodebaseMap, parse changed files, and persist."""

    indexing_service: IndexingService
    repository: CodebaseMapRepository

    def execute(self, cmd: IndexCodebaseCommand) -> IndexCodebaseResult:
        """Execute the indexing workflow.

        Args:
            cmd: The indexing command with repo ID, commit, and file contents.

        Returns:
            Result with number of files indexed and checkpoint.
        """
        existing_map = self.repository.load(cmd.repo_id)

        if existing_map is None:
            codebase_map = self.indexing_service.full_index(
                repo_id=cmd.repo_id,
                commit_sha=cmd.commit_sha,
                file_contents=cmd.file_contents,
            )
        else:
            codebase_map = self.indexing_service.incremental_update(
                codebase_map=existing_map,
                commit_sha=cmd.commit_sha,
                file_contents=cmd.file_contents,
            )
            self.repository.save(cmd.repo_id, codebase_map)

        checkpoint = Checkpoint(
            commit_sha=cmd.commit_sha,
            version=cmd.commit_sha[:12],
        )

        return IndexCodebaseResult(
            files_indexed=len(cmd.file_contents),
            checkpoint=checkpoint,
        )
