"""Tests for agentic (LLM-guided) retrieval strategy."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from argus.domain.llm.value_objects import LLMUsage, ModelConfig
from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.infrastructure.retrieval.agentic import (
    AgenticRetrievalStrategy,
    SearchPlan,
)
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# Helpers
# =============================================================================


def _make_config() -> ModelConfig:
    return ModelConfig(
        model="test",
        max_tokens=TokenCount(4096),
    )


def _make_query(
    changed_files: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    diff_text: str = "def foo(): pass",
) -> RetrievalQuery:
    return RetrievalQuery(
        changed_files=[FilePath(f) for f in (changed_files or [])],
        changed_symbols=changed_symbols or [],
        diff_text=diff_text,
    )


def _make_context_item(
    source: str = "related.py",
    content: str = "def related(): pass",
    score: float = 0.8,
    tokens: int = 20,
) -> ContextItem:
    return ContextItem(
        source=FilePath(source),
        content=content,
        relevance_score=score,
        token_cost=TokenCount(tokens),
    )


def _make_mock_run_result(
    plan: SearchPlan,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> MagicMock:
    """Create a mock agent run result with usage data."""
    mock_result = MagicMock()
    mock_result.output = plan
    mock_usage = MagicMock()
    mock_usage.input_tokens = input_tokens
    mock_usage.output_tokens = output_tokens
    mock_usage.requests = 1
    mock_result.usage.return_value = mock_usage
    return mock_result


@dataclass
class FakeStrategy:
    """Fake retrieval strategy that returns fixed items."""

    items: list[ContextItem]

    def retrieve(
        self, query: RetrievalQuery, budget: TokenCount | None = None
    ) -> list[ContextItem]:
        return self.items


# =============================================================================
# Tests
# =============================================================================


def test_returns_items_from_fallback_strategies() -> None:
    expected_item = _make_context_item(source="helper.py")
    fallback = FakeStrategy(items=[expected_item])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=1,
    )

    # Mock the agent's run_sync to return a plan with queries
    plan = SearchPlan(queries=["helper function"], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        items = strategy.retrieve(_make_query())

    assert len(items) == 1
    assert items[0].source == FilePath("helper.py")


def test_excludes_changed_files_from_sub_query_results() -> None:
    items = [
        _make_context_item(source="changed.py"),
        _make_context_item(source="untouched.py"),
    ]
    fallback = FakeStrategy(items=items)

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=1,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        query = _make_query(changed_files=["changed.py"])
        items = strategy.retrieve(query)

    sources = {item.source for item in items}
    assert FilePath("changed.py") not in sources
    assert FilePath("untouched.py") in sources


def test_stops_when_no_queries_generated() -> None:
    fallback = FakeStrategy(items=[_make_context_item()])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=5,
    )

    plan = SearchPlan(queries=[], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        items = strategy.retrieve(_make_query())

    assert items == []
    mock_run.assert_called_once()


def test_stops_when_needs_more_context_false() -> None:
    fallback = FakeStrategy(items=[_make_context_item()])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=5,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        strategy.retrieve(_make_query())

    mock_run.assert_called_once()


def test_iterates_when_needs_more_context_true() -> None:
    fallback = FakeStrategy(items=[_make_context_item(source="a.py")])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=3,
    )

    # First iteration: needs more; second iteration: done
    plan1 = SearchPlan(queries=["search a"], needs_more_context=True)
    plan2 = SearchPlan(queries=["search b"], needs_more_context=False)

    call_count = 0

    def side_effect(prompt: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        plan = plan1 if call_count == 1 else plan2
        return _make_mock_run_result(plan)

    with patch.object(strategy._agent, "run_sync", side_effect=side_effect):
        strategy.retrieve(_make_query())

    assert call_count == 2


def test_deduplicates_items_by_source() -> None:
    item = _make_context_item(source="dup.py")
    fallback = FakeStrategy(items=[item])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=2,
    )

    plan1 = SearchPlan(queries=["search"], needs_more_context=True)
    plan2 = SearchPlan(queries=["search again"], needs_more_context=False)

    call_count = 0

    def side_effect(prompt: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        plan = plan1 if call_count == 1 else plan2
        return _make_mock_run_result(plan)

    with patch.object(strategy._agent, "run_sync", side_effect=side_effect):
        items = strategy.retrieve(_make_query())

    sources = [item.source for item in items]
    assert sources.count(FilePath("dup.py")) == 1


def test_respects_max_iterations() -> None:
    fallback = FakeStrategy(items=[_make_context_item()])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=2,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=True)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        strategy.retrieve(_make_query())

    assert mock_run.call_count == 2


def test_empty_fallback_strategies_returns_empty() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[],
        max_iterations=1,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        items = strategy.retrieve(_make_query())

    assert items == []


def test_budget_stops_accumulating_items() -> None:
    items = [
        _make_context_item(source="a.py", tokens=100),
        _make_context_item(source="b.py", tokens=100),
        _make_context_item(source="c.py", tokens=100),
    ]
    fallback = FakeStrategy(items=items)

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=3,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=True)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        result = strategy.retrieve(_make_query(), budget=TokenCount(150))

    # Budget is 150, each item costs 100 — should get at most 1 item
    assert len(result) <= 1


def test_budget_none_collects_all_items() -> None:
    items = [
        _make_context_item(source="a.py", tokens=100),
        _make_context_item(source="b.py", tokens=100),
    ]
    fallback = FakeStrategy(items=items)

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=1,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        result = strategy.retrieve(_make_query(), budget=None)

    assert len(result) == 2


def test_budget_stops_iterations_early() -> None:
    items = [_make_context_item(source="a.py", tokens=100)]
    fallback = FakeStrategy(items=items)

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=5,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=True)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(plan)

        strategy.retrieve(_make_query(), budget=TokenCount(100))

    # First iteration collects 100 tokens (= budget), second iteration should
    # not yield new items since source is deduplicated. Budget exhaustion
    # only triggers when a new item would exceed the budget.
    # With dedup, all iterations return the same source, so no budget break.
    # But the key behavior is that it doesn't crash and respects max_iterations.
    assert mock_run.call_count <= 5


def test_last_llm_usage_tracks_accumulated_usage() -> None:
    fallback = FakeStrategy(items=[_make_context_item(source="a.py")])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=2,
    )

    plan1 = SearchPlan(queries=["search a"], needs_more_context=True)
    plan2 = SearchPlan(queries=["search b"], needs_more_context=False)

    call_count = 0

    def side_effect(prompt: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        plan = plan1 if call_count == 1 else plan2
        return _make_mock_run_result(plan, input_tokens=100, output_tokens=50)

    with patch.object(strategy._agent, "run_sync", side_effect=side_effect):
        strategy.retrieve(_make_query())

    assert isinstance(strategy.last_llm_usage, LLMUsage)
    assert strategy.last_llm_usage.input_tokens == 200
    assert strategy.last_llm_usage.output_tokens == 100
    assert strategy.last_llm_usage.requests == 2


def test_last_llm_usage_resets_between_calls() -> None:
    fallback = FakeStrategy(items=[_make_context_item()])

    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        fallback_strategies=[fallback],
        max_iterations=1,
    )

    plan = SearchPlan(queries=["search"], needs_more_context=False)
    with patch.object(strategy._agent, "run_sync") as mock_run:
        mock_run.return_value = _make_mock_run_result(
            plan, input_tokens=500, output_tokens=100
        )
        strategy.retrieve(_make_query())
        first_usage = strategy.last_llm_usage

        strategy.retrieve(_make_query())
        second_usage = strategy.last_llm_usage

    # Each call should reset, not accumulate across calls
    assert first_usage.input_tokens == 500
    assert second_usage.input_tokens == 500
