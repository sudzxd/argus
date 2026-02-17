"""Review Pull Request use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from argus.application.dto import ReviewPullRequestCommand, ReviewPullRequestResult
from argus.domain.context.entities import CodebaseMap
from argus.domain.context.repositories import CodebaseMapRepository
from argus.domain.context.services import IndexingService
from argus.domain.retrieval.value_objects import RetrievalQuery, RetrievalResult
from argus.domain.review.entities import Review
from argus.domain.review.repositories import ReviewPublisher
from argus.domain.review.services import NoiseFilter
from argus.domain.review.value_objects import ReviewRequest

# =============================================================================
# PROTOCOLS
# =============================================================================


class RetrievalOrchestratorPort(Protocol):
    """Port for retrieving relevant context."""

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...


class ReviewGeneratorPort(Protocol):
    """Port for generating a review from diff and context."""

    def generate(self, request: ReviewRequest) -> Review: ...


# =============================================================================
# USE CASE
# =============================================================================


@dataclass
class ReviewPullRequest:
    """Orchestrates the full PR review workflow.

    Steps:
    1. Index changed files into a codebase map
    2. Build retrieval query from changed files and diff
    3. Retrieve relevant context
    4. Generate review via LLM
    5. Filter noisy comments
    6. Publish review
    """

    indexing_service: IndexingService
    repository: CodebaseMapRepository
    orchestrator: RetrievalOrchestratorPort
    review_generator: ReviewGeneratorPort
    noise_filter: NoiseFilter
    publisher: ReviewPublisher

    def execute(self, cmd: ReviewPullRequestCommand) -> ReviewPullRequestResult:
        """Execute the review workflow.

        Args:
            cmd: The review command with PR details and file contents.

        Returns:
            Result with the review, context items used, and tokens consumed.
        """
        # 1. Index changed files
        codebase_map = self._index_changes(cmd)

        # 2. Build retrieval query
        query = RetrievalQuery(
            changed_files=cmd.changed_files,
            changed_symbols=self._extract_changed_symbols(codebase_map, cmd),
            diff_text=cmd.diff,
        )

        # 3. Retrieve context
        retrieval_result = self.orchestrator.retrieve(query)

        # 4. Generate review
        request = ReviewRequest(
            diff_text=cmd.diff,
            context=retrieval_result,
        )
        review = self.review_generator.generate(request)

        # 5. Filter noise
        filtered_comments = self.noise_filter.filter(review.comments)
        review = Review(
            summary=review.summary,
            comments=filtered_comments,
        )

        # 6. Publish
        self.publisher.publish(review, cmd.pr_number)

        return ReviewPullRequestResult(
            review=review,
            context_items_used=len(retrieval_result.items),
            tokens_used=retrieval_result.total_tokens,
        )

    def _index_changes(self, cmd: ReviewPullRequestCommand) -> CodebaseMap:
        """Index changed files into a codebase map."""
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

        return codebase_map

    def _extract_changed_symbols(
        self,
        codebase_map: CodebaseMap,
        cmd: ReviewPullRequestCommand,
    ) -> list[str]:
        """Extract symbol names from changed files."""
        symbols: list[str] = []
        for path in cmd.changed_files:
            if path in codebase_map:
                entry = codebase_map.get(path)
                symbols.extend(s.name for s in entry.symbols)
        return symbols
