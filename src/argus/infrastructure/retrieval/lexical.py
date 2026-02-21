"""Lexical retrieval strategy — BM25 sparse retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

import bm25s

from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.infrastructure.parsing.chunker import CodeChunk
from argus.shared.types import TokenCount

# =============================================================================
# STRATEGY
# =============================================================================

_DEFAULT_TOP_K = 10


@dataclass
class LexicalRetrievalStrategy:
    """Retrieves context using BM25 sparse retrieval over code chunks.

    Builds a BM25 index from chunk contents at construction time,
    then scores chunks against queries built from changed symbols
    and diff text.
    """

    chunks: list[CodeChunk]
    _top_k: int = _DEFAULT_TOP_K
    _index: bm25s.BM25 = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._index = bm25s.BM25()
        if self.chunks:
            corpus = [chunk.content for chunk in self.chunks]
            corpus_tokens = bm25s.tokenize(corpus, stopwords="en", show_progress=False)
            self._index.index(corpus_tokens, show_progress=False)

    def retrieve(
        self, query: RetrievalQuery, budget: TokenCount | None = None
    ) -> list[ContextItem]:
        """Retrieve context items relevant to the query via BM25."""
        if not self.chunks:
            return []

        query_text = self._build_query_text(query)
        if not query_text.strip():
            return []

        query_tokens = bm25s.tokenize([query_text], stopwords="en", show_progress=False)

        if budget is not None:
            avg_chunk_cost = self._avg_chunk_cost()
            k = max(1, min(int(budget) // max(1, avg_chunk_cost), len(self.chunks)))
        else:
            k = min(self._top_k, len(self.chunks))
        results, scores = self._index.retrieve(query_tokens, k=k, show_progress=False)

        changed = set(query.changed_files)
        items: list[ContextItem] = []

        # results and scores are 2D arrays (one row per query)
        for idx, score in zip(results[0], scores[0], strict=True):
            score_val = float(score)
            if score_val <= 0.0:
                continue
            chunk_idx = int(idx)
            if chunk_idx < 0 or chunk_idx >= len(self.chunks):
                continue
            chunk = self.chunks[chunk_idx]
            if chunk.source in changed:
                continue
            items.append(
                ContextItem(
                    source=chunk.source,
                    content=chunk.content,
                    relevance_score=score_val,
                    token_cost=chunk.token_cost,
                )
            )

        return items

    def _avg_chunk_cost(self) -> int:
        """Average token cost across all chunks."""
        if not self.chunks:
            return 1
        total = sum(int(c.token_cost) for c in self.chunks)
        return max(1, total // len(self.chunks))

    def _build_query_text(self, query: RetrievalQuery) -> str:
        """Build a query string from changed symbols and diff text."""
        parts: list[str] = []
        if query.changed_symbols:
            parts.append(" ".join(query.changed_symbols))
        if query.diff_text:
            parts.append(query.diff_text)
        return " ".join(parts)
