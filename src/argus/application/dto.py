"""Application-layer command and result DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.domain.context.entities import CodebaseMap
from argus.domain.context.value_objects import Checkpoint
from argus.domain.llm.value_objects import LLMUsage
from argus.domain.review.entities import Review
from argus.domain.review.value_objects import PRContext
from argus.shared.types import CommitSHA, FilePath, ReviewDepth, TokenCount

# =============================================================================
# INDEX CODEBASE
# =============================================================================


@dataclass(frozen=True)
class IndexCodebaseCommand:
    """Command to index (or re-index) a repository's codebase."""

    repo_id: str
    commit_sha: CommitSHA
    file_contents: dict[FilePath, str]


@dataclass(frozen=True)
class IndexCodebaseResult:
    """Result of a codebase indexing operation."""

    files_indexed: int
    checkpoint: Checkpoint


# =============================================================================
# REVIEW PULL REQUEST
# =============================================================================


@dataclass(frozen=True)
class ReviewPullRequestCommand:
    """Command to review a pull request."""

    repo_id: str
    pr_number: int
    commit_sha: CommitSHA
    diff: str
    changed_files: list[FilePath]
    file_contents: dict[FilePath, str]
    review_depth: ReviewDepth = ReviewDepth.STANDARD
    preloaded_map: CodebaseMap | None = None
    pr_context: PRContext | None = None


@dataclass(frozen=True)
class ReviewPullRequestResult:
    """Result of a pull request review."""

    review: Review
    context_items_used: int
    tokens_used: TokenCount
    llm_usage: LLMUsage = field(default_factory=LLMUsage)
