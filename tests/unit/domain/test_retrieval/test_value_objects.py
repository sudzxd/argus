"""Tests for Retrieval domain value objects."""

from __future__ import annotations

import pytest

from argus.domain.retrieval.value_objects import (
    ContextItem,
    RetrievalQuery,
    RetrievalResult,
)
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# RetrievalQuery
# =============================================================================


def test_retrieval_query_stores_fields(simple_query: RetrievalQuery) -> None:
    assert simple_query.changed_files == [FilePath("src/auth/login.py")]
    assert "login_user" in simple_query.changed_symbols
    assert "old_code" in simple_query.diff_text


def test_retrieval_query_is_immutable(simple_query: RetrievalQuery) -> None:
    with pytest.raises(AttributeError):
        simple_query.diff_text = "changed"  # type: ignore[misc]


# =============================================================================
# ContextItem
# =============================================================================


def test_context_item_stores_fields(context_item_high: ContextItem) -> None:
    assert context_item_high.source == FilePath("src/auth/login.py")
    assert context_item_high.relevance_score == 0.95
    assert context_item_high.token_cost == TokenCount(100)


def test_context_item_is_immutable(context_item_high: ContextItem) -> None:
    with pytest.raises(AttributeError):
        context_item_high.relevance_score = 0.0  # type: ignore[misc]


# =============================================================================
# RetrievalResult
# =============================================================================


def test_retrieval_result_stores_items(
    context_item_high: ContextItem,
    context_item_medium: ContextItem,
) -> None:
    result = RetrievalResult(items=[context_item_high, context_item_medium])

    assert len(result.items) == 2


def test_retrieval_result_total_tokens(
    context_item_high: ContextItem,
    context_item_medium: ContextItem,
) -> None:
    result = RetrievalResult(items=[context_item_high, context_item_medium])

    assert result.total_tokens == TokenCount(300)


def test_retrieval_result_empty() -> None:
    result = RetrievalResult(items=[])

    assert len(result.items) == 0
    assert result.total_tokens == TokenCount(0)


def test_retrieval_result_total_tokens_returns_token_count_type(
    context_item_high: ContextItem,
    context_item_medium: ContextItem,
) -> None:
    result = RetrievalResult(items=[context_item_high, context_item_medium])
    assert isinstance(result.total_tokens, TokenCount)


def test_retrieval_result_empty_total_tokens_returns_token_count_type() -> None:
    result = RetrievalResult(items=[])
    assert isinstance(result.total_tokens, TokenCount)


def test_retrieval_result_is_immutable(
    context_item_high: ContextItem,
) -> None:
    result = RetrievalResult(items=[context_item_high])

    with pytest.raises(AttributeError):
        result.items = []  # type: ignore[misc]
