"""Tests for LLM domain value objects."""

from __future__ import annotations

import pytest

from argus.domain.llm.value_objects import ModelConfig, TokenBudget
from argus.shared.types import TokenCount

# =============================================================================
# ModelConfig
# =============================================================================


def test_model_config_stores_fields(anthropic_config: ModelConfig) -> None:
    assert anthropic_config.model == "anthropic:claude-sonnet-4-5-20250929"
    assert anthropic_config.max_tokens == TokenCount(128_000)


def test_model_config_temperature_defaults_zero(
    anthropic_config: ModelConfig,
) -> None:
    assert anthropic_config.temperature == 0.0


def test_model_config_custom_temperature() -> None:
    config = ModelConfig(
        model="openai:gpt-4o",
        max_tokens=TokenCount(4_096),
        temperature=0.7,
    )
    assert config.temperature == 0.7


def test_model_config_is_immutable(anthropic_config: ModelConfig) -> None:
    with pytest.raises(AttributeError):
        anthropic_config.model = "changed"  # type: ignore[misc]


# =============================================================================
# TokenBudget
# =============================================================================


def test_token_budget_stores_fields(token_budget: TokenBudget) -> None:
    assert token_budget.total == TokenCount(128_000)
    assert token_budget.retrieval_ratio == 0.6
    assert token_budget.generation_ratio == 0.4


def test_token_budget_retrieval_tokens(token_budget: TokenBudget) -> None:
    assert token_budget.retrieval_tokens == TokenCount(76_800)


def test_token_budget_generation_tokens(token_budget: TokenBudget) -> None:
    assert token_budget.generation_tokens == TokenCount(51_200)


def test_token_budget_ratios_must_not_exceed_one() -> None:
    with pytest.raises(ValueError, match="ratio"):
        TokenBudget(
            total=TokenCount(100_000),
            retrieval_ratio=0.7,
            generation_ratio=0.5,
        )


def test_token_budget_is_immutable(token_budget: TokenBudget) -> None:
    with pytest.raises(AttributeError):
        token_budget.total = TokenCount(0)  # type: ignore[misc]
