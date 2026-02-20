"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.shared.exceptions import ConfigurationError

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_DIMENSION = 384


def _load_and_encode(model_name: str, texts: list[str]) -> list[list[float]]:
    """Load model and encode texts (untyped SDK)."""
    import sentence_transformers  # type: ignore[import-untyped]

    model = sentence_transformers.SentenceTransformer(model_name)  # pyright: ignore[reportUnknownVariableType]
    embeddings = model.encode(texts)  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
    return [e.tolist() for e in embeddings]  # type: ignore[no-any-return]


@dataclass
class LocalEmbeddingProvider:
    """Embedding provider using sentence-transformers locally."""

    model_name: str = _DEFAULT_MODEL
    _dimension: int = field(default=_DEFAULT_DIMENSION, init=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using a local sentence-transformers model."""
        try:
            result = _load_and_encode(self.model_name, texts)
        except ImportError as e:
            msg = "sentence-transformers package required for local embeddings"
            raise ConfigurationError(msg) from e

        if result:
            self._dimension = len(result[0])
        return result

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._dimension
