"""Typed exception hierarchy for Argus."""

from __future__ import annotations

from argus.shared.types import FilePath

# =============================================================================
# BASE
# =============================================================================


class ArgusError(Exception):
    """Base exception for all Argus errors."""


# =============================================================================
# CONTEXT
# =============================================================================


class IndexingError(ArgusError):
    """Failed to parse or index a file."""

    def __init__(self, path: FilePath, reason: str) -> None:
        self.path = path
        super().__init__(f"Failed to index {path}: {reason}")


class CheckpointError(ArgusError):
    """Failed to create or load a checkpoint."""


class GraphInconsistencyError(ArgusError):
    """Dependency graph invariant violated."""


# =============================================================================
# RETRIEVAL
# =============================================================================


class BudgetExceededError(ArgusError):
    """Retrieval result exceeds token budget."""

    def __init__(self, budget: int, requested: int) -> None:
        self.budget = budget
        self.requested = requested
        super().__init__(
            f"Token budget exceeded: {requested} requested, {budget} available"
        )


class StrategyError(ArgusError):
    """A retrieval strategy failed."""


# =============================================================================
# REVIEW
# =============================================================================


class GenerationError(ArgusError):
    """LLM failed to produce a parseable review."""


class PublishError(ArgusError):
    """Failed to post comments to GitHub."""


# =============================================================================
# LLM
# =============================================================================


class ProviderError(ArgusError):
    """LLM provider API call failed."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        super().__init__(f"Provider '{provider}' error: {reason}")


class RateLimitError(ArgusError):
    """Provider rate limit hit."""

    def __init__(self, provider: str, retry_after: float | None = None) -> None:
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"Rate limited by '{provider}'")


class TokenLimitError(ArgusError):
    """Prompt exceeds model's context window."""

    def __init__(self, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(
            f"Token limit exceeded: {required} required, {available} available"
        )


# =============================================================================
# CONFIGURATION
# =============================================================================


class ConfigurationError(ArgusError):
    """Invalid or missing configuration."""
