"""Value objects for the Review bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.domain.retrieval.value_objects import RetrievalResult
from argus.shared.types import FilePath

# =============================================================================
# VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class ReviewSummary:
    """High-level assessment of a pull request."""

    description: str
    risks: list[str]
    strengths: list[str]
    verdict: str


@dataclass(frozen=True)
class ReviewRequest:
    """Input bundle for review generation."""

    diff_text: str
    context: RetrievalResult
    strictness: str = "normal"
    ignored_paths: list[FilePath] = field(default_factory=list[FilePath])
