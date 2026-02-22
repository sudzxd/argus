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

        Raises:
            ValueError: If strategy_budgets length doesn't match strategies.
        """
        if self.strategy_budgets is not None and len(self.strategy_budgets) != len(
            self.strategies
        ):
            msg = (
                f"strategy_budgets length ({len(self.strategy_budgets)}) "
                f"must match strategies length ({len(self.strategies)})"
            )
            raise ValueError(msg)

        budgets: list[TokenCount | None]
        if self.strategy_budgets is not None:
            budgets = list(self.strategy_budgets)
        else:
            budgets = [None] * len(self.strategies)

        all_items: list[ContextItem] = []
        for strategy, budget in zip(self.strategies, budgets, strict=True):
            all_items.extend(strategy.retrieve(query, budget=budget))

        return self._ranker.rank(all_items, self.budget)
