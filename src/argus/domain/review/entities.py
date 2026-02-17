"""Entities for the Review bounded context."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.review.value_objects import ReviewSummary
from argus.shared.types import Category, FilePath, LineRange, Severity

# =============================================================================
# ENTITIES
# =============================================================================


@dataclass(frozen=True)
class ReviewComment:
    """A single finding in a pull request review."""

    file: FilePath
    line_range: LineRange
    severity: Severity
    category: Category
    body: str
    confidence: float
    suggestion: str | None = None


@dataclass(frozen=True)
class Review:
    """Aggregate root — the complete review of a pull request."""

    summary: ReviewSummary
    comments: list[ReviewComment]

    def comments_by_severity(self, severity: Severity) -> list[ReviewComment]:
        """Filter comments by severity level."""
        return [c for c in self.comments if c.severity == severity]

    @property
    def has_critical(self) -> bool:
        """Whether the review contains any critical findings."""
        return any(c.severity == Severity.CRITICAL for c in self.comments)

    def __len__(self) -> int:
        return len(self.comments)
