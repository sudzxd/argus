"""Tests for Review domain entities."""

from __future__ import annotations

import pytest

from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewSummary
from argus.shared.types import (
    Category,
    FilePath,
    LineRange,
    Severity,
)

# =============================================================================
# ReviewComment
# =============================================================================


def test_review_comment_stores_fields(critical_comment: ReviewComment) -> None:
    assert critical_comment.file == FilePath("src/auth/login.py")
    assert critical_comment.severity == Severity.CRITICAL
    assert critical_comment.category == Category.BUG
    assert "SQL injection" in critical_comment.body
    assert critical_comment.suggestion is not None
    assert critical_comment.confidence == 0.95


def test_review_comment_suggestion_optional() -> None:
    comment = ReviewComment(
        file=FilePath("a.py"),
        line_range=LineRange(start=1, end=1),
        severity=Severity.PRAISE,
        category=Category.STYLE,
        body="Nice work.",
        suggestion=None,
        confidence=0.9,
    )
    assert comment.suggestion is None


def test_review_comment_is_immutable(critical_comment: ReviewComment) -> None:
    with pytest.raises(AttributeError):
        critical_comment.severity = Severity.PRAISE  # type: ignore[misc]


# =============================================================================
# Review
# =============================================================================


def test_review_stores_summary_and_comments(sample_review: Review) -> None:
    assert sample_review.summary is not None
    assert len(sample_review.comments) == 2


def test_review_comments_by_severity(sample_review: Review) -> None:
    critical = sample_review.comments_by_severity(Severity.CRITICAL)

    assert len(critical) == 1
    assert critical[0].severity == Severity.CRITICAL


def test_review_comments_by_severity_empty(sample_review: Review) -> None:
    praise = sample_review.comments_by_severity(Severity.PRAISE)

    assert len(praise) == 0


def test_review_has_critical(sample_review: Review) -> None:
    assert sample_review.has_critical is True


def test_review_has_critical_false() -> None:
    review = Review(
        summary=ReviewSummary(
            description="All good.",
            risks=[],
            strengths=["Clean code."],
            verdict="Approved.",
        ),
        comments=[],
    )
    assert review.has_critical is False


def test_review_comment_count(sample_review: Review) -> None:
    assert len(sample_review) == 2
