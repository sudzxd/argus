"""Google Generative AI embedding provider."""

from __future__ import annotations

import os

from dataclasses import dataclass, field

from argus.shared.exceptions import ConfigurationError

_DEFAULT_MODEL = "text-embedding-004"
_DEFAULT_DIMENSION = 768


def _call_embed_api(api_key: str, model: str, texts: list[str]) -> list[list[float]]:
    """Call the Google genai embedding API (untyped SDK)."""
    from google import genai  # type: ignore[import-untyped]

    client = genai.Client(api_key=api_key)  # pyright: ignore[reportUnknownVariableType]
    result = client.models.embed_content(model=model, contents=texts)  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
    return [e.values for e in result.embeddings]  # type: ignore[no-any-return]


@dataclass
class GoogleEmbeddingProvider:
    """Embedding provider using the Google Generative AI SDK."""

    model_name: str = _DEFAULT_MODEL
    _dimension: int = field(default=_DEFAULT_DIMENSION, init=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the Google Generative AI API."""
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            msg = "GOOGLE_API_KEY required for Google embeddings"
            raise ConfigurationError(msg)

        try:
            embeddings = _call_embed_api(api_key, self.model_name, texts)
        except ImportError as e:
            msg = "google-genai package required for Google embeddings"
            raise ConfigurationError(msg) from e

        if embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._dimension
