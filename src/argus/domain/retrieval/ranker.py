"""Context ranking and budget enforcement."""

from __future__ import annotations

from argus.domain.retrieval.value_objects import ContextItem, RetrievalResult
from argus.shared.types import TokenCount

# =============================================================================
# RANKER
# =============================================================================


class ContextRanker:
    """Scores, deduplicates, and budget-constrains context items."""

    def rank(self, items: list[ContextItem], budget: TokenCount) -> RetrievalResult:
        """Rank items by relevance, deduplicate, and fit within budget.

        Args:
            items: Unranked context items from all strategies.
            budget: Maximum total token cost.

        Returns:
            Budget-constrained retrieval result with highest-relevance items.
        """
        deduped = self._deduplicate(items)
        sorted_items = sorted(deduped, key=lambda i: i.relevance_score, reverse=True)
        return self._fill_budget(sorted_items, budget)

    def _deduplicate(self, items: list[ContextItem]) -> list[ContextItem]:
        """Keep the highest-scored item per source file."""
        best: dict[str, ContextItem] = {}
        for item in items:
            key = str(item.source)
            if key not in best or item.relevance_score > best[key].relevance_score:
                best[key] = item
        return list(best.values())

    def _fill_budget(
        self, items: list[ContextItem], budget: TokenCount
    ) -> RetrievalResult:
        """Greedily fill the budget with highest-relevance items."""
        selected: list[ContextItem] = []
        remaining = int(budget)

        for item in items:
            if int(item.token_cost) <= remaining:
                selected.append(item)
                remaining -= int(item.token_cost)

        return RetrievalResult(items=selected)
