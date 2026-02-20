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
class CheckRun:
    """A single CI check run result."""

    name: str
    status: str
    conclusion: str | None
    summary: str | None


@dataclass(frozen=True)
class CIStatus:
    """Aggregate CI status for a commit."""

    conclusion: str | None
    checks: list[CheckRun]


@dataclass(frozen=True)
class GitHealth:
    """Git hygiene metrics for a pull request."""

    behind_by: int
    has_merge_commits: bool
    days_open: int


@dataclass(frozen=True)
class PRComment:
    """A comment on a pull request."""

    author: str
    body: str
    created_at: str
    file_path: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class RelatedItem:
    """An issue or PR related to the current pull request."""

    kind: str
    number: int
    title: str
    state: str
    body: str | None


@dataclass(frozen=True)
class PRContext:
    """Enriched PR metadata for holistic review."""

    title: str
    body: str
    author: str
    created_at: str
    labels: list[str]
    comments: list[PRComment]
    ci_status: CIStatus
    git_health: GitHealth
    related_items: list[RelatedItem]


@dataclass(frozen=True)
class ReviewRequest:
    """Input bundle for review generation."""

    diff_text: str
    context: RetrievalResult
    strictness: str = "normal"
    ignored_paths: list[FilePath] = field(default_factory=list[FilePath])
    codebase_outline_text: str | None = None
    codebase_patterns_text: str | None = None
    pr_context: PRContext | None = None
