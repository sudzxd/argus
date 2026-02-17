"""Tests for the ContextRanker."""

from __future__ import annotations

from argus.domain.retrieval.ranker import ContextRanker
from argus.domain.retrieval.value_objects import ContextItem
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# Ranking & Budgeting
# =============================================================================


def test_ranker_returns_items_within_budget(
    context_item_high: ContextItem,
    context_item_medium: ContextItem,
    context_item_low: ContextItem,
) -> None:
    ranker = ContextRanker()
    items = [context_item_high, context_item_medium, context_item_low]
    budget = TokenCount(350)

    result = ranker.rank(items, budget)

    assert result.total_tokens <= budget


def test_ranker_prioritizes_high_relevance(
    context_item_high: ContextItem,
    context_item_low: ContextItem,
) -> None:
    ranker = ContextRanker()
    items = [context_item_low, context_item_high]
    budget = TokenCount(150)

    result = ranker.rank(items, budget)

    assert result.items[0].source == context_item_high.source


def test_ranker_drops_items_exceeding_budget() -> None:
    ranker = ContextRanker()
    expensive = ContextItem(
        source=FilePath("big.py"),
        content="x" * 1000,
        relevance_score=0.5,
        token_cost=TokenCount(10_000),
    )
    budget = TokenCount(100)

    result = ranker.rank([expensive], budget)

    assert len(result.items) == 0


def test_ranker_deduplicates_same_source() -> None:
    ranker = ContextRanker()
    item_a = ContextItem(
        source=FilePath("a.py"),
        content="version 1",
        relevance_score=0.9,
        token_cost=TokenCount(100),
    )
    item_a_dup = ContextItem(
        source=FilePath("a.py"),
        content="version 2",
        relevance_score=0.8,
        token_cost=TokenCount(100),
    )
    budget = TokenCount(500)

    result = ranker.rank([item_a, item_a_dup], budget)

    sources = [item.source for item in result.items]
    assert sources.count(FilePath("a.py")) == 1


def test_ranker_keeps_higher_scored_duplicate() -> None:
    ranker = ContextRanker()
    high = ContextItem(
        source=FilePath("a.py"),
        content="high",
        relevance_score=0.9,
        token_cost=TokenCount(100),
    )
    low = ContextItem(
        source=FilePath("a.py"),
        content="low",
        relevance_score=0.3,
        token_cost=TokenCount(100),
    )
    budget = TokenCount(500)

    result = ranker.rank([low, high], budget)

    assert result.items[0].content == "high"


def test_ranker_empty_input() -> None:
    ranker = ContextRanker()

    result = ranker.rank([], TokenCount(1000))

    assert len(result.items) == 0
    assert result.total_tokens == TokenCount(0)
