"""Tests for embedding providers and factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argus.infrastructure.retrieval.embeddings.factory import (
    create_embedding_provider,
)
from argus.shared.exceptions import ConfigurationError

# =============================================================================
# Factory tests
# =============================================================================


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


# =============================================================================
# Google provider tests
# =============================================================================


def test_google_embed_missing_api_key_raises() -> None:
    from argus.infrastructure.retrieval.embeddings.google_embeddings import (
        GoogleEmbeddingProvider,
    )

    provider = GoogleEmbeddingProvider()
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ConfigurationError, match="GOOGLE_API_KEY"),
    ):
        provider.embed(["hello"])


@patch("argus.infrastructure.retrieval.embeddings.google_embeddings._call_embed_api")
def test_google_embed_returns_embeddings(mock_api: MagicMock) -> None:
    from argus.infrastructure.retrieval.embeddings.google_embeddings import (
        GoogleEmbeddingProvider,
    )

    mock_api.return_value = [[0.1, 0.2], [0.3, 0.4]]
    provider = GoogleEmbeddingProvider()
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
        result = provider.embed(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert provider.dimension == 2


@patch("argus.infrastructure.retrieval.embeddings.google_embeddings._call_embed_api")
def test_google_embed_import_error_raises_config_error(mock_api: MagicMock) -> None:
    from argus.infrastructure.retrieval.embeddings.google_embeddings import (
        GoogleEmbeddingProvider,
    )

    mock_api.side_effect = ImportError("no google")
    provider = GoogleEmbeddingProvider()
    with (
        patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}),
        pytest.raises(ConfigurationError, match="google-genai"),
    ):
        provider.embed(["hello"])


# =============================================================================
# OpenAI provider tests
# =============================================================================


def test_openai_embed_missing_api_key_raises() -> None:
    from argus.infrastructure.retrieval.embeddings.openai_embeddings import (
        OpenAIEmbeddingProvider,
    )

    provider = OpenAIEmbeddingProvider()
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ConfigurationError, match="OPENAI_API_KEY"),
    ):
        provider.embed(["hello"])


@patch("argus.infrastructure.retrieval.embeddings.openai_embeddings._call_embed_api")
def test_openai_embed_returns_embeddings(mock_api: MagicMock) -> None:
    from argus.infrastructure.retrieval.embeddings.openai_embeddings import (
        OpenAIEmbeddingProvider,
    )

    mock_api.return_value = [[0.1, 0.2, 0.3]]
    provider = OpenAIEmbeddingProvider()
    with patch.dict("os.environ", {"OPENAI_API_KEY": "fake"}):
        result = provider.embed(["hello"])

    assert result == [[0.1, 0.2, 0.3]]
    assert provider.dimension == 3


@patch("argus.infrastructure.retrieval.embeddings.openai_embeddings._call_embed_api")
def test_openai_embed_import_error_raises_config_error(mock_api: MagicMock) -> None:
    from argus.infrastructure.retrieval.embeddings.openai_embeddings import (
        OpenAIEmbeddingProvider,
    )

    mock_api.side_effect = ImportError("no openai")
    provider = OpenAIEmbeddingProvider()
    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "fake"}),
        pytest.raises(ConfigurationError, match="openai"),
    ):
        provider.embed(["hello"])


# =============================================================================
# Local provider tests
# =============================================================================


@patch("argus.infrastructure.retrieval.embeddings.local_embeddings._encode")
@patch("argus.infrastructure.retrieval.embeddings.local_embeddings._get_model")
def test_local_embed_returns_embeddings(
    mock_get_model: MagicMock, mock_encode: MagicMock
) -> None:
    from argus.infrastructure.retrieval.embeddings.local_embeddings import (
        LocalEmbeddingProvider,
        _model_cache,
    )

    _model_cache.clear()
    mock_get_model.return_value = MagicMock()
    mock_encode.return_value = [[0.5, 0.6]]
    provider = LocalEmbeddingProvider()
    result = provider.embed(["hello"])

    assert result == [[0.5, 0.6]]
    assert provider.dimension == 2
    _model_cache.clear()


@patch("argus.infrastructure.retrieval.embeddings.local_embeddings._get_model")
def test_local_embed_import_error_raises_config_error(
    mock_get_model: MagicMock,
) -> None:
    from argus.infrastructure.retrieval.embeddings.local_embeddings import (
        LocalEmbeddingProvider,
        _model_cache,
    )

    _model_cache.clear()
    mock_get_model.side_effect = ImportError("no sentence_transformers")
    provider = LocalEmbeddingProvider()
    with pytest.raises(ConfigurationError, match="sentence-transformers"):
        provider.embed(["hello"])
    _model_cache.clear()


# =============================================================================
# Dimension set-once tests
# =============================================================================


@patch("argus.infrastructure.retrieval.embeddings.google_embeddings._call_embed_api")
def test_google_dimension_not_mutated_on_second_call(mock_api: MagicMock) -> None:
    from argus.infrastructure.retrieval.embeddings.google_embeddings import (
        GoogleEmbeddingProvider,
    )

    mock_api.return_value = [[0.1, 0.2, 0.3]]
    provider = GoogleEmbeddingProvider()
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
        provider.embed(["first"])
        assert provider.dimension == 3

        # Second call returns different-length vectors — dimension stays 3.
        mock_api.return_value = [[0.1, 0.2]]
        provider.embed(["second"])
        assert provider.dimension == 3


@patch("argus.infrastructure.retrieval.embeddings.openai_embeddings._call_embed_api")
def test_openai_dimension_not_mutated_on_second_call(mock_api: MagicMock) -> None:
    from argus.infrastructure.retrieval.embeddings.openai_embeddings import (
        OpenAIEmbeddingProvider,
    )

    mock_api.return_value = [[0.1, 0.2, 0.3]]
    provider = OpenAIEmbeddingProvider()
    with patch.dict("os.environ", {"OPENAI_API_KEY": "fake"}):
        provider.embed(["first"])
        assert provider.dimension == 3

        mock_api.return_value = [[0.1, 0.2]]
        provider.embed(["second"])
        assert provider.dimension == 3


@patch("argus.infrastructure.retrieval.embeddings.local_embeddings._encode")
@patch("argus.infrastructure.retrieval.embeddings.local_embeddings._get_model")
def test_local_dimension_not_mutated_on_second_call(
    mock_get_model: MagicMock, mock_encode: MagicMock
) -> None:
    from argus.infrastructure.retrieval.embeddings.local_embeddings import (
        LocalEmbeddingProvider,
        _model_cache,
    )

    _model_cache.clear()
    mock_get_model.return_value = MagicMock()
    mock_encode.return_value = [[0.1, 0.2, 0.3]]
    provider = LocalEmbeddingProvider()

    provider.embed(["first"])
    assert provider.dimension == 3

    mock_encode.return_value = [[0.1, 0.2]]
    provider.embed(["second"])
    assert provider.dimension == 3
    _model_cache.clear()
