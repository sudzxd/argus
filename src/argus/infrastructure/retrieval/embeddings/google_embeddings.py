"""Google Generative AI embedding provider."""

from __future__ import annotations

import logging
import os
import time

from dataclasses import dataclass, field

from argus.shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-embedding-001"
_DEFAULT_DIMENSION = 3072
_MAX_CHARS_PER_TEXT = 7500  # ~2048 tokens, stay under per-text limit
_BATCH_SIZE = 100  # Larger batches = fewer requests = less rate-limit pressure
_MAX_RETRIES = 7
_INITIAL_BACKOFF = 5.0  # seconds — generous to avoid cascading 429s
_REQUEST_DELAY = 1.0  # seconds between requests to stay under RPM limit


def _embed_batch_with_retry(
    client: object, model: str, texts: list[str]
) -> list[list[float]]:
    """Embed a single batch with exponential backoff on rate limits."""
    backoff = _INITIAL_BACKOFF
    for attempt in range(_MAX_RETRIES):
        try:
            result = client.models.embed_content(model=model, contents=texts)  # type: ignore[union-attr]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
            return [e.values for e in result.embeddings]  # type: ignore[no-any-return]
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt < _MAX_RETRIES - 1:
                logger.info(
                    "Rate limited, waiting %.0fs (attempt %d/%d)",
                    backoff,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
    return []  # unreachable, but satisfies type checker


def _call_embed_api(api_key: str, model: str, texts: list[str]) -> list[list[float]]:
    """Call the Google genai embedding API with batching and rate limiting."""
    from google import genai  # type: ignore[import-untyped]

    client = genai.Client(api_key=api_key)  # pyright: ignore[reportUnknownVariableType]

    # Truncate oversized texts and track which indices have content.
    cleaned: list[str] = []
    valid_indices: list[int] = []
    for i, t in enumerate(texts):
        stripped = t.strip()
        if stripped:
            cleaned.append(stripped[:_MAX_CHARS_PER_TEXT])
            valid_indices.append(i)

    if not cleaned:
        return [[0.0] * _DEFAULT_DIMENSION for _ in texts]

    # Process batches sequentially with a delay to respect rate limits.
    clean_embeddings: list[list[float]] = []
    num_batches = (len(cleaned) + _BATCH_SIZE - 1) // _BATCH_SIZE
    for i in range(0, len(cleaned), _BATCH_SIZE):
        batch = cleaned[i : i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        logger.info(
            "Embedding batch %d/%d (%d texts)", batch_num, num_batches, len(batch)
        )
        result = _embed_batch_with_retry(client, model, batch)  # pyright: ignore[reportUnknownArgumentType]
        clean_embeddings.extend(result)
        # Delay between batches (skip after the last one).
        if i + _BATCH_SIZE < len(cleaned):
            time.sleep(_REQUEST_DELAY)

    # Map back to original indices, using zero vectors for empty texts.
    dim = len(clean_embeddings[0]) if clean_embeddings else _DEFAULT_DIMENSION
    all_embeddings: list[list[float]] = [[0.0] * dim for _ in texts]
    for idx, emb in zip(valid_indices, clean_embeddings, strict=True):
        all_embeddings[idx] = emb

    return all_embeddings


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
