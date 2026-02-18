"""pydantic-ai Agent factory.

Creates pydantic-ai ``Agent`` instances from domain ``ModelConfig``.
"""

from __future__ import annotations

from pydantic_ai import Agent

from argus.domain.llm.value_objects import ModelConfig


def create_agent[T](
    config: ModelConfig,
    output_type: type[T],
    system_prompt: str,
) -> Agent[None, T]:
    """Build a pydantic-ai Agent from a ModelConfig.

    Args:
        config: Model configuration (model string, max_tokens, temperature).
        output_type: The structured output type for the agent.
        system_prompt: System prompt for the agent.

    Returns:
        A configured pydantic-ai Agent ready for ``run_sync`` / ``run``.
    """
    return Agent(
        model=config.model,
        output_type=output_type,
        system_prompt=system_prompt,
        model_settings={
            "max_tokens": int(config.max_tokens),
            "temperature": config.temperature,
        },
        retries=3,
    )
