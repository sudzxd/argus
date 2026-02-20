"""Tests for semantic retrieval strategy."""

from __future__ import annotations

from argus.domain.context.value_objects import EmbeddingIndex, ShardId
from argus.domain.retrieval.value_objects import RetrievalQuery
from argus.infrastructure.parsing.chunker import CodeChunk
from argus.infrastructure.retrieval.semantic import (
    SemanticRetrievalStrategy,
    _cosine_similarity,
)
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# Cosine similarity
# =============================================================================


def test_cosine_similarity_identical_vectors() -> None:
    a = [1.0, 0.0, 0.0]
    assert abs(_cosine_similarity(a, a) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_opposite_vectors() -> None:
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6


def test_cosine_similarity_zero_vector() -> None:
    a = [0.0, 0.0]
    b = [1.0, 0.0]
    assert _cosine_similarity(a, b) == 0.0


# =============================================================================
# Semantic retrieval
# =============================================================================


class FakeEmbeddingProvider:
    """Fake provider that returns pre-set embeddings."""

    def __init__(self, embeddings: list[list[float]]) -> None:
        self._embeddings = embeddings
        self._call_count = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._embeddings[self._call_count : self._call_count + len(texts)]
        self._call_count += len(texts)
        return result

    @property
    def dimension(self) -> int:
        if self._embeddings:
            return len(self._embeddings[0])
        return 0


def _make_chunk(path: str, symbol: str, content: str) -> CodeChunk:
    return CodeChunk(
        source=FilePath(path),
        symbol_name=symbol,
        content=content,
        token_cost=TokenCount(len(content) // 4),
    )


def test_retrieve_returns_top_k_by_similarity() -> None:
    # Two chunks with known embeddings.
    chunk_a = _make_chunk("a.py", "func_a", "def func_a(): pass")
    chunk_b = _make_chunk("b.py", "func_b", "def func_b(): pass")

    index = EmbeddingIndex(
        shard_id=ShardId("."),
        embeddings=[
            [1.0, 0.0, 0.0],  # chunk_a — close to query
            [0.0, 1.0, 0.0],  # chunk_b — far from query
        ],
        chunk_ids=["a.py:func_a", "b.py:func_b"],
        dimension=3,
        model="test",
    )

    # Query embedding is closest to chunk_a.
    provider = FakeEmbeddingProvider(
        embeddings=[[0.9, 0.1, 0.0]]  # query
    )

    strategy = SemanticRetrievalStrategy(
        provider=provider,
        embedding_indices=[index],
        chunks=[chunk_a, chunk_b],
        top_k=2,
    )

    query = RetrievalQuery(
        changed_files=[FilePath("c.py")],
        changed_symbols=["func_c"],
        diff_text="+ func_c",
    )
    items = strategy.retrieve(query)

    assert len(items) == 2
    # First item should be chunk_a (higher similarity).
    assert items[0].source == FilePath("a.py")
    assert items[0].relevance_score > items[1].relevance_score


def test_retrieve_respects_budget() -> None:
    chunk = _make_chunk("a.py", "func", "x" * 100)

    index = EmbeddingIndex(
        shard_id=ShardId("."),
        embeddings=[[1.0, 0.0]],
        chunk_ids=["a.py:func"],
        dimension=2,
        model="test",
    )

    provider = FakeEmbeddingProvider(embeddings=[[1.0, 0.0]])

    strategy = SemanticRetrievalStrategy(
        provider=provider,
        embedding_indices=[index],
        chunks=[chunk],
        top_k=10,
    )

    query = RetrievalQuery(
        changed_files=[FilePath("b.py")],
        changed_symbols=["sym"],
        diff_text="diff",
    )
    # Budget of 1 token — chunk costs 25 tokens, so nothing fits.
    items = strategy.retrieve(query, budget=TokenCount(1))
    assert len(items) == 0


def test_retrieve_empty_query() -> None:
    strategy = SemanticRetrievalStrategy(
        provider=FakeEmbeddingProvider(embeddings=[[0.0]]),
        embedding_indices=[],
        chunks=[],
    )
    query = RetrievalQuery(
        changed_files=[],
        changed_symbols=[],
        diff_text="",
    )
    items = strategy.retrieve(query)
    assert items == []
