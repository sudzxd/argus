"""Domain services for the Review bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.domain.review.entities import ReviewComment
from argus.shared.types import FilePath

# =============================================================================
# NOISE FILTER
# =============================================================================


@dataclass
class NoiseFilter:
    """Drops low-confidence and ignored-path comments."""

    confidence_threshold: float
    ignored_paths: list[FilePath] = field(default_factory=list[FilePath])

    def filter(self, comments: list[ReviewComment]) -> list[ReviewComment]:
        """Remove comments below confidence threshold or in ignored paths.

        Args:
            comments: Unfiltered review comments.

        Returns:
            Comments that pass both confidence and path checks.
        """
        return [
            c
            for c in comments
            if c.confidence >= self.confidence_threshold
            and not self._is_ignored(c.file)
        ]

    def _is_ignored(self, path: FilePath) -> bool:
        return any(str(path).startswith(str(ignored)) for ignored in self.ignored_paths)
