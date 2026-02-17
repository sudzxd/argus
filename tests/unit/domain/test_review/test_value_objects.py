"""Tests for Review domain value objects."""

from __future__ import annotations

import pytest

from argus.domain.review.value_objects import ReviewRequest, ReviewSummary
from argus.shared.types import FilePath

# =============================================================================
# ReviewSummary
# =============================================================================


def test_review_summary_stores_fields(review_summary: ReviewSummary) -> None:
    assert "JWT authentication" in review_summary.description
    assert len(review_summary.risks) == 1
    assert len(review_summary.strengths) == 1
    assert review_summary.verdict == "Changes needed."


def test_review_summary_is_immutable(review_summary: ReviewSummary) -> None:
    with pytest.raises(AttributeError):
        review_summary.verdict = "approved"  # type: ignore[misc]


# =============================================================================
# ReviewRequest
# =============================================================================


def test_review_request_stores_fields(review_request: ReviewRequest) -> None:
    assert "old" in review_request.diff_text
    assert len(review_request.context.items) == 1
    assert review_request.strictness == "normal"
    assert FilePath("tests/*") in review_request.ignored_paths


def test_review_request_is_immutable(review_request: ReviewRequest) -> None:
    with pytest.raises(AttributeError):
        review_request.diff_text = "changed"  # type: ignore[misc]
