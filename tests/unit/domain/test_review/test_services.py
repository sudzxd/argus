"""Tests for Review domain services."""

from __future__ import annotations

from argus.domain.review.entities import ReviewComment
from argus.domain.review.services import NoiseFilter
from argus.shared.types import (
    Category,
    FilePath,
    LineRange,
    Severity,
)

# =============================================================================
# NoiseFilter
# =============================================================================


def test_noise_filter_drops_below_threshold(
    critical_comment: ReviewComment,
    low_confidence_comment: ReviewComment,
) -> None:
    noise_filter = NoiseFilter(confidence_threshold=0.5)

    filtered = noise_filter.filter([critical_comment, low_confidence_comment])

    assert len(filtered) == 1
    assert filtered[0].severity == Severity.CRITICAL


def test_noise_filter_drops_ignored_paths(
    critical_comment: ReviewComment,
) -> None:
    ignored_comment = ReviewComment(
        file=FilePath("tests/test_auth.py"),
        line_range=LineRange(start=1, end=5),
        severity=Severity.SUGGESTION,
        category=Category.STYLE,
        body="Nitpick in test.",
        suggestion=None,
        confidence=0.9,
    )
    noise_filter = NoiseFilter(
        confidence_threshold=0.5,
        ignored_paths=[FilePath("tests/")],
    )

    filtered = noise_filter.filter([critical_comment, ignored_comment])

    assert len(filtered) == 1
    assert filtered[0].file == FilePath("src/auth/login.py")


def test_noise_filter_keeps_all_above_threshold(
    critical_comment: ReviewComment,
    suggestion_comment: ReviewComment,
) -> None:
    noise_filter = NoiseFilter(confidence_threshold=0.5)

    filtered = noise_filter.filter([critical_comment, suggestion_comment])

    assert len(filtered) == 2


def test_noise_filter_empty_input() -> None:
    noise_filter = NoiseFilter(confidence_threshold=0.5)

    filtered = noise_filter.filter([])

    assert len(filtered) == 0
