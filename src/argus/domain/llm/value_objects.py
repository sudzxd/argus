"""Value objects for the LLM bounded context."""

from __future__ import annotations

from dataclasses import dataclass

from argus.shared.types import TokenCount

# =============================================================================
# VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class LLMUsage:
    """Aggregated token usage from LLM API calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: LLMUsage) -> LLMUsage:
        return LLMUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            requests=self.requests + other.requests,
        )


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for an LLM model via pydantic-ai.

    The ``model`` field uses pydantic-ai model strings, e.g.
    ``"anthropic:claude-sonnet-4-5-20250929"`` or ``"openai:gpt-4o"``.
    """

    model: str
    max_tokens: TokenCount
    temperature: float = 0.0


@dataclass(frozen=True)
class TokenBudget:
    """Token allocation split between retrieval and generation."""

    total: TokenCount
    retrieval_ratio: float
    generation_ratio: float

    def __post_init__(self) -> None:
        if self.retrieval_ratio + self.generation_ratio > 1.0:
            msg = (
                f"retrieval_ratio ({self.retrieval_ratio}) + "
                f"generation_ratio ({self.generation_ratio}) "
                f"must not exceed 1.0"
            )
            raise ValueError(msg)

    @property
    def retrieval_tokens(self) -> TokenCount:
        """Tokens available for retrieval context."""
        return TokenCount(int(self.total * self.retrieval_ratio))

    @property
    def generation_tokens(self) -> TokenCount:
        """Tokens available for LLM generation."""
        return TokenCount(int(self.total * self.generation_ratio))
