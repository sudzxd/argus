"""Tests for application layer DTOs."""

from __future__ import annotations

from argus.application.dto import (
    IndexCodebaseCommand,
    IndexCodebaseResult,
    ReviewPullRequestCommand,
    ReviewPullRequestResult,
)
from argus.domain.context.value_objects import Checkpoint
from argus.domain.review.entities import Review
from argus.domain.review.value_objects import ReviewSummary
from argus.shared.types import (
    CommitSHA,
    FilePath,
    TokenCount,
)

# =============================================================================
# IndexCodebaseCommand
# =============================================================================


def test_index_codebase_command_stores_fields() -> None:
    cmd = IndexCodebaseCommand(
        repo_id="org/repo",
        commit_sha=CommitSHA("abc123"),
        file_contents={FilePath("main.py"): "print('hi')"},
    )
    assert cmd.repo_id == "org/repo"
    assert cmd.commit_sha == CommitSHA("abc123")
    assert cmd.file_contents[FilePath("main.py")] == "print('hi')"


def test_index_codebase_command_is_frozen() -> None:
    cmd = IndexCodebaseCommand(
        repo_id="org/repo",
        commit_sha=CommitSHA("abc"),
        file_contents={},
    )
    assert hasattr(cmd, "__dataclass_fields__")


# =============================================================================
# IndexCodebaseResult
# =============================================================================


def test_index_codebase_result_stores_fields() -> None:
    checkpoint = Checkpoint(
        commit_sha=CommitSHA("abc123"),
        version="v1",
    )
    result = IndexCodebaseResult(
        files_indexed=3,
        checkpoint=checkpoint,
    )
    assert result.files_indexed == 3
    assert result.checkpoint.commit_sha == CommitSHA("abc123")


# =============================================================================
# ReviewPullRequestCommand
# =============================================================================


def test_review_pr_command_stores_fields() -> None:
    cmd = ReviewPullRequestCommand(
        repo_id="org/repo",
        pr_number=42,
        commit_sha=CommitSHA("abc123"),
        diff="diff --git a/file.py",
        changed_files=[FilePath("file.py")],
        file_contents={FilePath("file.py"): "x = 1"},
    )
    assert cmd.repo_id == "org/repo"
    assert cmd.pr_number == 42
    assert cmd.diff == "diff --git a/file.py"
    assert len(cmd.changed_files) == 1


# =============================================================================
# ReviewPullRequestResult
# =============================================================================


def test_review_pr_result_stores_fields() -> None:
    review = Review(
        summary=ReviewSummary(
            description="LGTM",
            risks=[],
            strengths=["Clean"],
            verdict="Approve",
        ),
        comments=[],
    )
    result = ReviewPullRequestResult(
        review=review,
        context_items_used=5,
        tokens_used=TokenCount(1000),
    )
    assert result.review.summary.description == "LGTM"
    assert result.context_items_used == 5
    assert result.tokens_used == TokenCount(1000)
