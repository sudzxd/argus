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
    strategy_budgets: list[TokenCount] | None = None
    _ranker: ContextRanker = field(default_factory=ContextRanker)

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Run all strategies, combine results, rank and budget.

        Args:
            query: What context to retrieve.

        Returns:
            Ranked, deduplicated, budget-constrained retrieval result.
        """
        all_items: list[ContextItem] = []
        for i, strategy in enumerate(self.strategies):
            strat_budget = self.strategy_budgets[i] if self.strategy_budgets else None
            all_items.extend(strategy.retrieve(query, budget=strat_budget))

        return self._ranker.rank(all_items, self.budget)
