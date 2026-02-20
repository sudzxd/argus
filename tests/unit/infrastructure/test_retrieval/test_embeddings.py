"""Tests for embedding provider factory."""

from __future__ import annotations

import pytest

from argus.infrastructure.retrieval.embeddings.factory import (
    create_embedding_provider,
)
from argus.shared.exceptions import ConfigurationError


def test_factory_google_prefix() -> None:
    provider = create_embedding_provider("google-emb:text-embedding-004")
    from argus.infrastructure.retrieval.embeddings.google_embeddings import (
        GoogleEmbeddingProvider,
    )

    assert isinstance(provider, GoogleEmbeddingProvider)
    assert provider.model_name == "text-embedding-004"


def test_factory_openai_prefix() -> None:
    provider = create_embedding_provider("openai-emb:text-embedding-3-small")
    from argus.infrastructure.retrieval.embeddings.openai_embeddings import (
        OpenAIEmbeddingProvider,
    )

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.model_name == "text-embedding-3-small"


def test_factory_local_prefix() -> None:
    provider = create_embedding_provider("local:all-MiniLM-L6-v2")
    from argus.infrastructure.retrieval.embeddings.local_embeddings import (
        LocalEmbeddingProvider,
    )

    assert isinstance(provider, LocalEmbeddingProvider)
    assert provider.model_name == "all-MiniLM-L6-v2"


def test_factory_unknown_prefix_raises() -> None:
    with pytest.raises(ConfigurationError, match="Unknown embedding model"):
        create_embedding_provider("unknown:model")
