"""Fixtures for Review domain tests."""

from __future__ import annotations

import pytest

from argus.domain.retrieval.value_objects import ContextItem, RetrievalResult
from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewRequest, ReviewSummary
from argus.shared.types import (
    Category,
    FilePath,
    LineRange,
    Severity,
    TokenCount,
)


@pytest.fixture
def critical_comment() -> ReviewComment:
    return ReviewComment(
        file=FilePath("src/auth/login.py"),
        line_range=LineRange(start=15, end=15),
        severity=Severity.CRITICAL,
        category=Category.BUG,
        body="Possible SQL injection via unsanitized input.",
        suggestion="Use parameterized queries.",
        confidence=0.95,
    )


@pytest.fixture
def suggestion_comment() -> ReviewComment:
    return ReviewComment(
        file=FilePath("src/utils/helpers.py"),
        line_range=LineRange(start=42, end=44),
        severity=Severity.SUGGESTION,
        category=Category.STYLE,
        body="Consider extracting this into a named constant.",
        suggestion="TIMEOUT_SECONDS = 30",
        confidence=0.6,
    )


@pytest.fixture
def low_confidence_comment() -> ReviewComment:
    return ReviewComment(
        file=FilePath("src/main.py"),
        line_range=LineRange(start=1, end=1),
        severity=Severity.SUGGESTION,
        category=Category.STYLE,
        body="Maybe rename this variable.",
        suggestion=None,
        confidence=0.3,
    )


@pytest.fixture
def review_summary() -> ReviewSummary:
    return ReviewSummary(
        description="Adds JWT authentication to the login endpoint.",
        risks=["SQL injection in query builder."],
        strengths=["Good test coverage."],
        verdict="Changes needed.",
    )


@pytest.fixture
def sample_review(
    review_summary: ReviewSummary,
    critical_comment: ReviewComment,
    suggestion_comment: ReviewComment,
) -> Review:
    return Review(
        summary=review_summary,
        comments=[critical_comment, suggestion_comment],
    )


@pytest.fixture
def review_request() -> ReviewRequest:
    return ReviewRequest(
        diff_text="- old\n+ new",
        context=RetrievalResult(
            items=[
                ContextItem(
                    source=FilePath("src/auth/login.py"),
                    content="def login_user(): ...",
                    relevance_score=0.9,
                    token_cost=TokenCount(100),
                ),
            ]
        ),
        strictness="normal",
        ignored_paths=[FilePath("tests/*")],
    )
