"""Tests for Retrieval domain services and protocols."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.retrieval.services import RetrievalOrchestrator
from argus.domain.retrieval.strategies import RetrievalStrategy
from argus.domain.retrieval.value_objects import (
    ContextItem,
    RetrievalQuery,
    RetrievalResult,
)
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# RetrievalStrategy protocol conformance
# =============================================================================


def test_retrieval_strategy_protocol_accepts_conforming_class(
    simple_query: RetrievalQuery,
) -> None:
    @dataclass
    class FakeStrategy:
        def retrieve(self, query: RetrievalQuery) -> list[ContextItem]:
            return [
                ContextItem(
                    source=FilePath("fake.py"),
                    content="fake",
                    relevance_score=0.5,
                    token_cost=TokenCount(10),
                ),
            ]

    strategy: RetrievalStrategy = FakeStrategy()
    items = strategy.retrieve(simple_query)

    assert len(items) == 1
    assert items[0].source == FilePath("fake.py")


# =============================================================================
# RetrievalOrchestrator
# =============================================================================


def _make_strategy(source: str, score: float, tokens: int) -> RetrievalStrategy:
    @dataclass
    class _Strategy:
        def retrieve(self, query: RetrievalQuery) -> list[ContextItem]:
            return [
                ContextItem(
                    source=FilePath(source),
                    content=f"from {source}",
                    relevance_score=score,
                    token_cost=TokenCount(tokens),
                ),
            ]

    return _Strategy()


def test_orchestrator_combines_strategies(
    simple_query: RetrievalQuery,
) -> None:
    structural = _make_strategy("structural.py", 0.9, 100)
    lexical = _make_strategy("lexical.py", 0.7, 100)

    orchestrator = RetrievalOrchestrator(
        strategies=[structural, lexical],
        budget=TokenCount(500),
    )

    result = orchestrator.retrieve(simple_query)

    sources = {item.source for item in result.items}
    assert FilePath("structural.py") in sources
    assert FilePath("lexical.py") in sources


def test_orchestrator_respects_budget(
    simple_query: RetrievalQuery,
) -> None:
    big = _make_strategy("big.py", 0.9, 400)
    small = _make_strategy("small.py", 0.8, 100)

    orchestrator = RetrievalOrchestrator(
        strategies=[big, small],
        budget=TokenCount(300),
    )

    result = orchestrator.retrieve(simple_query)

    assert result.total_tokens <= TokenCount(300)


def test_orchestrator_no_strategies(
    simple_query: RetrievalQuery,
) -> None:
    orchestrator = RetrievalOrchestrator(
        strategies=[],
        budget=TokenCount(500),
    )

    result = orchestrator.retrieve(simple_query)

    assert len(result.items) == 0


def test_orchestrator_returns_retrieval_result(
    simple_query: RetrievalQuery,
) -> None:
    strategy = _make_strategy("a.py", 0.9, 50)
    orchestrator = RetrievalOrchestrator(
        strategies=[strategy],
        budget=TokenCount(500),
    )

    result = orchestrator.retrieve(simple_query)

    assert isinstance(result, RetrievalResult)
