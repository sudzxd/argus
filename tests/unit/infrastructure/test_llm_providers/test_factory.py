"""Tests for pydantic-ai Agent factory."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from argus.domain.llm.value_objects import ModelConfig
from argus.infrastructure.llm_providers.factory import create_agent
from argus.shared.types import TokenCount


class _DummyOutput(BaseModel):
    answer: str


def _make_config(
    model: str = "test",
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> ModelConfig:
    return ModelConfig(
        model=model,
        max_tokens=TokenCount(max_tokens),
        temperature=temperature,
    )


def test_create_agent_returns_agent() -> None:
    agent = create_agent(
        config=_make_config(),
        output_type=_DummyOutput,
        system_prompt="You are helpful.",
    )
    assert isinstance(agent, Agent)


def test_create_agent_uses_output_type() -> None:
    agent = create_agent(
        config=_make_config(),
        output_type=_DummyOutput,
        system_prompt="You are helpful.",
    )
    assert agent.output_type == _DummyOutput


def test_create_agent_sets_system_prompt() -> None:
    prompt = "Review code carefully."
    agent = create_agent(
        config=_make_config(),
        output_type=_DummyOutput,
        system_prompt=prompt,
    )
    # pydantic-ai stores system prompts as a tuple of callables/strings
    assert any(prompt in str(p) for p in agent._system_prompts)


def test_create_agent_accepts_custom_temperature() -> None:
    agent = create_agent(
        config=_make_config(temperature=0.7),
        output_type=_DummyOutput,
        system_prompt="Be creative.",
    )
    assert isinstance(agent, Agent)
