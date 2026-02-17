"""Application-layer command and result DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.context.value_objects import Checkpoint
from argus.domain.review.entities import Review
from argus.shared.types import CommitSHA, FilePath, TokenCount

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


@dataclass(frozen=True)
class ReviewPullRequestResult:
    """Result of a pull request review."""

    review: Review
    context_items_used: int
    tokens_used: TokenCount
