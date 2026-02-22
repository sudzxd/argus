"""Factory for creating embedding providers from model strings."""

from __future__ import annotations

from argus.domain.retrieval.embeddings import EmbeddingProvider
from argus.shared.exceptions import ConfigurationError


def create_embedding_provider(model_str: str) -> EmbeddingProvider:
    """Create an embedding provider from a prefixed model string.

    Supported prefixes:
        - ``google-emb:`` — Google Generative AI embeddings
        - ``openai-emb:`` — OpenAI embeddings
        - ``local:`` — Local sentence-transformers model

    Args:
        model_str: Prefixed model identifier (e.g. ``google-emb:text-embedding-004``).

    Returns:
        An EmbeddingProvider instance.

    Raises:
        ConfigurationError: If the prefix is unknown.
    """
    if model_str.startswith("google-emb:"):
        from argus.infrastructure.retrieval.embeddings.google_embeddings import (
            GoogleEmbeddingProvider,
        )

        model_name = model_str[len("google-emb:") :]
        return GoogleEmbeddingProvider(model_name=model_name)

    if model_str.startswith("openai-emb:"):
        from argus.infrastructure.retrieval.embeddings.openai_embeddings import (
            OpenAIEmbeddingProvider,
        )

        model_name = model_str[len("openai-emb:") :]
        return OpenAIEmbeddingProvider(model_name=model_name)

    if model_str.startswith("local:"):
        from argus.infrastructure.retrieval.embeddings.local_embeddings import (
            LocalEmbeddingProvider,
        )

        model_name = model_str[len("local:") :]
        return LocalEmbeddingProvider(model_name=model_name)

    msg = (
        f"Unknown embedding model prefix in '{model_str}'. "
        "Use google-emb:, openai-emb:, or local:"
    )
    raise ConfigurationError(msg)
