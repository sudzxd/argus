"""Tests for GitHub review publisher."""

from __future__ import annotations

from unittest.mock import MagicMock

from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewSummary
from argus.infrastructure.constants import SeverityLabel
from argus.infrastructure.github.publisher import GitHubReviewPublisher
from argus.shared.types import Category, FilePath, LineRange, Severity

# =============================================================================
# Helpers
# =============================================================================


def _make_review(
    comments: list[ReviewComment] | None = None,
) -> Review:
    return Review(
        summary=ReviewSummary(
            description="Looks good overall.",
            risks=["May break on edge cases"],
            strengths=["Clean code"],
            verdict="Approve with suggestions",
        ),
        comments=comments or [],
    )


def _make_comment(
    severity: Severity = Severity.WARNING,
    file: str = "src/main.py",
    start: int = 10,
    end: int = 15,
) -> ReviewComment:
    return ReviewComment(
        file=FilePath(file),
        line_range=LineRange(start=start, end=end),
        severity=severity,
        category=Category.BUG,
        body="This could be an issue.",
        confidence=0.85,
        suggestion="Consider adding a null check.",
    )


# =============================================================================
# Tests
# =============================================================================


def test_publish_with_comments_uses_post_review() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)
    review = _make_review(comments=[_make_comment()])

    publisher.publish(review, pr_number=42)

    mock_client.post_review.assert_called_once()
    mock_client.post_issue_comment.assert_not_called()


def test_publish_without_comments_uses_issue_comment() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)
    review = _make_review(comments=[])

    publisher.publish(review, pr_number=42)

    mock_client.post_issue_comment.assert_called_once()
    mock_client.post_review.assert_not_called()


def test_publish_formats_summary_correctly() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)
    review = _make_review()

    publisher.publish(review, pr_number=42)

    body = mock_client.post_issue_comment.call_args.kwargs["body"]
    assert "Looks good overall." in body
    assert "May break on edge cases" in body
    assert "Clean code" in body
    assert "Approve with suggestions" in body


def test_publish_formats_comment_with_severity_label() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)

    comment = _make_comment(severity=Severity.CRITICAL)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted_comments = mock_client.post_review.call_args.kwargs["comments"]
    assert len(posted_comments) == 1
    assert SeverityLabel.CRITICAL in posted_comments[0]["body"]


def test_publish_includes_suggestion_in_comment() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)

    comment = _make_comment()
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted_comments = mock_client.post_review.call_args.kwargs["comments"]
    assert "Suggestion:" in posted_comments[0]["body"]


def test_publish_comment_includes_line_range() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)

    comment = _make_comment(start=5, end=10)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted = mock_client.post_review.call_args.kwargs["comments"][0]
    assert posted["line"] == 10
    assert posted["start_line"] == 5


def test_publish_single_line_comment_omits_start_line() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)

    comment = _make_comment(start=10, end=10)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted = mock_client.post_review.call_args.kwargs["comments"][0]
    assert posted["line"] == 10
    assert "start_line" not in posted
