"""Embedding provider protocol for semantic retrieval."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Interface for text embedding providers."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        ...

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        ...
