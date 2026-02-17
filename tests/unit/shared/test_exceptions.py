"""Tests for shared exception hierarchy."""

from __future__ import annotations

import pytest

from argus.shared.exceptions import (
    ArgusError,
    BudgetExceededError,
    ConfigurationError,
    GenerationError,
    GraphInconsistencyError,
    IndexingError,
    ProviderError,
    PublishError,
    RateLimitError,
    StrategyError,
    TokenLimitError,
)
from argus.shared.types import FilePath

# =============================================================================
# Hierarchy
# =============================================================================


def test_all_exceptions_inherit_from_argus_error() -> None:
    exceptions = [
        IndexingError,
        GraphInconsistencyError,
        BudgetExceededError,
        StrategyError,
        GenerationError,
        PublishError,
        ProviderError,
        RateLimitError,
        TokenLimitError,
        ConfigurationError,
    ]
    for exc_class in exceptions:
        assert issubclass(exc_class, ArgusError)


def test_argus_error_inherits_from_exception() -> None:
    assert issubclass(ArgusError, Exception)


# =============================================================================
# Structured Context
# =============================================================================


def test_indexing_error_carries_path() -> None:
    path = FilePath("src/main.py")
    err = IndexingError(path=path, reason="unsupported language")

    assert err.path == path
    assert "src/main.py" in str(err)
    assert "unsupported language" in str(err)


def test_provider_error_carries_provider_name() -> None:
    err = ProviderError(provider="anthropic", reason="invalid api key")

    assert err.provider == "anthropic"
    assert "anthropic" in str(err)
    assert "invalid api key" in str(err)


def test_rate_limit_error_carries_retry_after() -> None:
    err = RateLimitError(provider="openai", retry_after=30.0)

    assert err.retry_after == 30.0
    assert "openai" in str(err)


def test_token_limit_error_carries_counts() -> None:
    err = TokenLimitError(required=200_000, available=128_000)

    assert err.required == 200_000
    assert err.available == 128_000


def test_budget_exceeded_error_carries_budget() -> None:
    err = BudgetExceededError(budget=50_000, requested=75_000)

    assert err.budget == 50_000
    assert err.requested == 75_000


# =============================================================================
# Catchability
# =============================================================================


def test_indexing_error_catchable_as_argus_error() -> None:
    with pytest.raises(ArgusError):
        raise IndexingError(path=FilePath("x.py"), reason="parse failure")


def test_provider_error_catchable_as_argus_error() -> None:
    with pytest.raises(ArgusError):
        raise ProviderError(provider="ollama", reason="connection refused")
