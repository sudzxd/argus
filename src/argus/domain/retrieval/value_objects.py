"""Value objects for the Retrieval bounded context."""

from __future__ import annotations

from dataclasses import dataclass

from argus.shared.types import FilePath, TokenCount

# =============================================================================
# VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class RetrievalQuery:
    """Encodes what context is needed for a PR review."""

    changed_files: list[FilePath]
    changed_symbols: list[str]
    diff_text: str


@dataclass(frozen=True)
class ContextItem:
    """A single piece of retrieved context."""

    source: FilePath
    content: str
    relevance_score: float
    token_cost: TokenCount


@dataclass(frozen=True)
class RetrievalResult:
    """Ranked, budgeted context ready for the review generator."""

    items: list[ContextItem]

    @property
    def total_tokens(self) -> TokenCount:
        """Total token cost of all items."""
        return sum((item.token_cost for item in self.items), start=TokenCount(0))
