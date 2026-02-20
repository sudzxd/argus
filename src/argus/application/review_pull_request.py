"""Review Pull Request use case."""

from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Protocol

from argus.application.dto import ReviewPullRequestCommand, ReviewPullRequestResult
from argus.domain.context.entities import CodebaseMap
from argus.domain.context.repositories import CodebaseMapRepository
from argus.domain.context.services import IndexingService
from argus.domain.llm.value_objects import LLMUsage
from argus.domain.memory.value_objects import (
    CodebaseMemory,
    CodebaseOutline,
    PatternEntry,
)
from argus.domain.retrieval.value_objects import RetrievalQuery, RetrievalResult
from argus.domain.review.entities import Review
from argus.domain.review.repositories import ReviewPublisher
from argus.domain.review.services import NoiseFilter
from argus.domain.review.value_objects import ReviewRequest
from argus.shared.exceptions import ArgusError
from argus.shared.types import FilePath, ReviewDepth

logger = logging.getLogger(__name__)

# =============================================================================
# PROTOCOLS
# =============================================================================


class RetrievalOrchestratorPort(Protocol):
    """Port for retrieving relevant context."""

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...


class ReviewGeneratorPort(Protocol):
    """Port for generating a review from diff and context."""

    def generate(self, request: ReviewRequest) -> tuple[Review, LLMUsage]: ...


class OutlineRendererPort(Protocol):
    """Port for rendering codebase outlines."""

    def render(
        self,
        codebase_map: CodebaseMap,
        changed_files: list[FilePath],
    ) -> tuple[str, CodebaseOutline]: ...


class MemoryRepositoryPort(Protocol):
    """Port for codebase memory persistence."""

    def load(self, repo_id: str) -> CodebaseMemory | None: ...
    def save(self, memory: CodebaseMemory) -> None: ...


class ProfileServicePort(Protocol):
    """Port for building/updating codebase memory profiles."""

    def build_profile(
        self,
        repo_id: str,
        outline: CodebaseOutline,
        outline_text: str,
    ) -> CodebaseMemory: ...

    def update_profile(
        self,
        existing: CodebaseMemory,
        outline: CodebaseOutline,
        outline_text: str,
    ) -> CodebaseMemory: ...


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
    4. Build memory context (outline + patterns based on review depth)
    5. Generate review via LLM
    6. Filter noisy comments
    7. Publish review
    """

    indexing_service: IndexingService
    repository: CodebaseMapRepository
    orchestrator: RetrievalOrchestratorPort
    review_generator: ReviewGeneratorPort
    noise_filter: NoiseFilter
    publisher: ReviewPublisher
    outline_renderer: OutlineRendererPort | None = None
    memory_repository: MemoryRepositoryPort | None = None
    profile_service: ProfileServicePort | None = None

    def execute(self, cmd: ReviewPullRequestCommand) -> ReviewPullRequestResult:
        """Execute the review workflow."""
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

        # 4. Build memory context
        outline_text, patterns_text = self._build_memory_context(codebase_map, cmd)

        # 5. Generate review
        request = ReviewRequest(
            diff_text=cmd.diff,
            context=retrieval_result,
            codebase_outline_text=outline_text,
            codebase_patterns_text=patterns_text,
            pr_context=cmd.pr_context,
        )
        review, generation_usage = self.review_generator.generate(request)

        # 6. Filter noise
        filtered_comments = self.noise_filter.filter(review.comments)
        review = Review(
            summary=review.summary,
            comments=filtered_comments,
        )

        # 7. Publish
        self.publisher.publish(review, cmd.pr_number)

        return ReviewPullRequestResult(
            review=review,
            context_items_used=len(retrieval_result.items),
            tokens_used=retrieval_result.total_tokens,
            llm_usage=generation_usage,
        )

    def _index_changes(self, cmd: ReviewPullRequestCommand) -> CodebaseMap:
        """Index changed files into a codebase map.

        If ``cmd.preloaded_map`` is set, uses it directly instead of
        loading from the repository (avoids loading shards that were
        never pulled to disk in selective mode).
        """
        existing_map = cmd.preloaded_map or self.repository.load(cmd.repo_id)

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

    def _build_memory_context(
        self,
        codebase_map: CodebaseMap,
        cmd: ReviewPullRequestCommand,
    ) -> tuple[str | None, str | None]:
        """Build outline and patterns text based on review depth.

        Returns:
            (outline_text, patterns_text) — either may be None.
        """
        depth = cmd.review_depth

        if depth == ReviewDepth.QUICK or self.outline_renderer is None:
            return None, None

        # Standard and deep: render outline.
        outline_text, outline = self.outline_renderer.render(
            codebase_map, cmd.changed_files
        )
        if not outline_text:
            return None, None

        logger.info(
            "Rendered outline: %d files, %d chars",
            outline.file_count,
            len(outline_text),
        )

        if depth != ReviewDepth.DEEP:
            return outline_text, None

        # Deep: also load/build patterns.
        patterns_text = self._build_patterns_text(cmd.repo_id, outline, outline_text)
        return outline_text, patterns_text

    def _build_patterns_text(
        self,
        repo_id: str,
        outline: CodebaseOutline,
        outline_text: str,
    ) -> str | None:
        """Load or build codebase patterns, return rendered text."""
        if self.memory_repository is None or self.profile_service is None:
            return None

        existing = self.memory_repository.load(repo_id)

        try:
            if existing is None:
                memory = self.profile_service.build_profile(
                    repo_id, outline, outline_text
                )
            else:
                memory = self.profile_service.update_profile(
                    existing, outline, outline_text
                )
            self.memory_repository.save(memory)
        except ArgusError:
            logger.exception("Pattern analysis failed, continuing without patterns")
            return None

        if not memory.patterns:
            return None

        return _render_patterns(memory.patterns)


def _render_patterns(patterns: list[PatternEntry]) -> str:
    """Format patterns as readable text for the LLM prompt."""
    lines: list[str] = []
    for p in patterns:
        lines.append(
            f"- [{p.category.value}] {p.description} (confidence: {p.confidence:.1f})"
        )
        for ex in p.examples[:2]:
            lines.append(f"  Example: {ex}")
    return "\n".join(lines)
