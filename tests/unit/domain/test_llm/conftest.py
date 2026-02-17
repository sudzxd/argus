"""Fixtures for LLM domain tests."""

from __future__ import annotations

import pytest

from argus.domain.llm.value_objects import ModelConfig, TokenBudget
from argus.shared.types import TokenCount


@pytest.fixture
def anthropic_config() -> ModelConfig:
    return ModelConfig(
        model="anthropic:claude-sonnet-4-5-20250929",
        max_tokens=TokenCount(128_000),
    )


@pytest.fixture
def ollama_config() -> ModelConfig:
    return ModelConfig(
        model="ollama:llama3",
        max_tokens=TokenCount(8_000),
    )


@pytest.fixture
def token_budget() -> TokenBudget:
    return TokenBudget(
        total=TokenCount(128_000),
        retrieval_ratio=0.6,
        generation_ratio=0.4,
    )
