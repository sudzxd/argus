"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus.shared.exceptions import ConfigurationError

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_DIMENSION = 384


_model_cache: dict[str, object] = {}


def _get_model(model_name: str) -> object:
    """Get or create a cached SentenceTransformer model."""
    if model_name not in _model_cache:
        import sentence_transformers  # type: ignore[import-untyped]

        _model_cache[model_name] = sentence_transformers.SentenceTransformer(model_name)  # pyright: ignore[reportUnknownVariableType]
    return _model_cache[model_name]


def _encode(model: object, texts: list[str]) -> list[list[float]]:
    """Encode texts with a loaded model."""
    embeddings = model.encode(texts)  # type: ignore[union-attr]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
    return [e.tolist() for e in embeddings]  # type: ignore[no-any-return]


@dataclass
class LocalEmbeddingProvider:
    """Embedding provider using sentence-transformers locally."""

    model_name: str = _DEFAULT_MODEL
    _dimension: int = field(default=_DEFAULT_DIMENSION, init=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using a local sentence-transformers model."""
        try:
            model = _get_model(self.model_name)
            result = _encode(model, texts)
        except ImportError as e:
            msg = "sentence-transformers package required for local embeddings"
            raise ConfigurationError(msg) from e

        if result and self._dimension == _DEFAULT_DIMENSION:
            self._dimension = len(result[0])
        return result

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._dimension
