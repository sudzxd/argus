"""Semantic retrieval strategy — embedding-based similarity."""

from __future__ import annotations

import math

from dataclasses import dataclass, field

from argus.domain.context.value_objects import EmbeddingIndex
from argus.domain.retrieval.embeddings import EmbeddingProvider
from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.infrastructure.constants import CHARS_PER_TOKEN
from argus.infrastructure.parsing.chunker import CodeChunk
from argus.shared.types import FilePath, TokenCount


@dataclass
class SemanticRetrievalStrategy:
    """Retrieves context by embedding similarity against pre-computed indices."""

    provider: EmbeddingProvider
    embedding_indices: list[EmbeddingIndex]
    chunks: list[CodeChunk]
    top_k: int = 10

    _chunk_lookup: dict[str, CodeChunk] = field(
        default_factory=dict[str, CodeChunk],
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        for chunk in self.chunks:
            chunk_id = f"{chunk.source}:{chunk.symbol_name}"
            self._chunk_lookup[chunk_id] = chunk

    def retrieve(
        self,
        query: RetrievalQuery,
        budget: TokenCount | None = None,
    ) -> list[ContextItem]:
        """Retrieve context items by embedding similarity.

        Args:
            query: The retrieval query with changed files/symbols/diff.
            budget: Optional token budget to limit results.

        Returns:
            List of context items ranked by cosine similarity.
        """
        query_text = self._build_query_text(query)
        if not query_text:
            return []

        query_embedding = self.provider.embed([query_text])[0]

        scored: list[tuple[float, str]] = []
        for index in self.embedding_indices:
            for i, chunk_id in enumerate(index.chunk_ids):
                if i < len(index.embeddings):
                    score = _cosine_similarity(query_embedding, index.embeddings[i])
                    scored.append((score, chunk_id))

        scored.sort(key=lambda x: x[0], reverse=True)

        items: list[ContextItem] = []
        used_tokens = 0
        for score, chunk_id in scored[: self.top_k]:
            chunk = self._chunk_lookup.get(chunk_id)
            if chunk is None:
                continue
            token_cost = max(1, len(chunk.content) // CHARS_PER_TOKEN)
            if budget is not None and used_tokens + token_cost > budget:
                break
            items.append(
                ContextItem(
                    source=FilePath(str(chunk.source)),
                    content=chunk.content,
                    relevance_score=score,
                    token_cost=TokenCount(token_cost),
                )
            )
            used_tokens += token_cost

        return items

    def _build_query_text(self, query: RetrievalQuery) -> str:
        """Build a text query from changed symbols and diff."""
        parts: list[str] = []
        if query.changed_symbols:
            parts.append(" ".join(query.changed_symbols))
        if query.diff_text:
            # Use a truncated diff summary to keep query focused.
            parts.append(query.diff_text[:500])
        return " ".join(parts)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
