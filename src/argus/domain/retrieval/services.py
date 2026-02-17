"""Domain services for the Retrieval bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.domain.retrieval.ranker import ContextRanker
from argus.domain.retrieval.strategies import RetrievalStrategy
from argus.domain.retrieval.value_objects import (
    ContextItem,
    RetrievalQuery,
    RetrievalResult,
)
from argus.shared.types import TokenCount

# =============================================================================
# ORCHESTRATOR
# =============================================================================


@dataclass
class RetrievalOrchestrator:
    """Composes multiple retrieval strategies and ranks their results."""

    strategies: list[RetrievalStrategy]
    budget: TokenCount
    _ranker: ContextRanker = field(default_factory=ContextRanker)

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Run all strategies, combine results, rank and budget.

        Args:
            query: What context to retrieve.

        Returns:
            Ranked, deduplicated, budget-constrained retrieval result.
        """
        all_items: list[ContextItem] = []
        for strategy in self.strategies:
            all_items.extend(strategy.retrieve(query))

        return self._ranker.rank(all_items, self.budget)
