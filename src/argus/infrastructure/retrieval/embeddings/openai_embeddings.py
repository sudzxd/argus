"""OpenAI embedding provider."""

from __future__ import annotations

import os

from dataclasses import dataclass, field

from argus.shared.exceptions import ConfigurationError

_DEFAULT_MODEL = "text-embedding-3-small"
_DEFAULT_DIMENSION = 1536


def _call_embed_api(api_key: str, model: str, texts: list[str]) -> list[list[float]]:
    """Call the OpenAI embedding API (untyped SDK)."""
    from openai import OpenAI  # type: ignore[import-untyped]

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in response.data]  # type: ignore[no-any-return]


@dataclass
class OpenAIEmbeddingProvider:
    """Embedding provider using the OpenAI API."""

    model_name: str = _DEFAULT_MODEL
    _dimension: int = field(default=_DEFAULT_DIMENSION, init=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the OpenAI API."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            msg = "OPENAI_API_KEY required for OpenAI embeddings"
            raise ConfigurationError(msg)

        try:
            embeddings = _call_embed_api(api_key, self.model_name, texts)
        except ImportError as e:
            msg = "openai package required for OpenAI embeddings"
            raise ConfigurationError(msg) from e

        if embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._dimension
