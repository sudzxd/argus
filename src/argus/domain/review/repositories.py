"""Repository protocols for the Review bounded context."""

from __future__ import annotations

from typing import Protocol

from argus.domain.review.entities import Review

# =============================================================================
# PROTOCOLS
# =============================================================================


class ReviewPublisher(Protocol):
    """Interface for publishing reviews to a pull request."""

    def publish(self, review: Review, pr_number: int) -> None:
        """Post the review to the pull request."""
        ...
