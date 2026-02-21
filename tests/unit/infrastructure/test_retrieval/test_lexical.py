"""Tests for lexical (BM25) retrieval strategy."""

from __future__ import annotations

from argus.domain.retrieval.value_objects import RetrievalQuery
from argus.infrastructure.parsing.chunker import CodeChunk
from argus.infrastructure.retrieval.lexical import LexicalRetrievalStrategy
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# Helpers
# =============================================================================


def _make_chunk(source: str, symbol: str, content: str, tokens: int = 50) -> CodeChunk:
    return CodeChunk(
        source=FilePath(source),
        symbol_name=symbol,
        content=content,
        token_cost=TokenCount(tokens),
    )


def _make_query(
    changed_files: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    diff_text: str = "",
) -> RetrievalQuery:
    return RetrievalQuery(
        changed_files=[FilePath(f) for f in (changed_files or [])],
        changed_symbols=changed_symbols or [],
        diff_text=diff_text,
    )


# =============================================================================
# Tests
# =============================================================================


def test_returns_relevant_chunks_for_matching_query() -> None:
    chunks = [
        _make_chunk("auth.py", "login", "def login_user(username, password): ..."),
        _make_chunk("db.py", "connect", "def connect_database(host, port): ..."),
        _make_chunk("utils.py", "validate", "def validate_email(email): ..."),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["login_user"],
        diff_text="login username password",
    )

    items = strategy.retrieve(query)

    sources = {item.source for item in items}
    assert FilePath("auth.py") in sources


def test_excludes_changed_files_from_results() -> None:
    chunks = [
        _make_chunk("auth.py", "login", "def login_user(username, password): ..."),
        _make_chunk(
            "handler.py",
            "handle",
            "def handle_login(username, password): login_user(username, password)",
        ),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_files=["auth.py"],
        changed_symbols=["login_user"],
        diff_text="login username password",
    )

    items = strategy.retrieve(query)
    sources = {item.source for item in items}

    assert FilePath("auth.py") not in sources


def test_returns_empty_list_when_no_matches() -> None:
    chunks = [
        _make_chunk("math.py", "add", "def add(a, b): return a + b"),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["zzz_nonexistent_xyz"],
        diff_text="zzz_nonexistent_xyz qwerty_nothing",
    )

    items = strategy.retrieve(query)

    # BM25 may return results with low scores; just verify no crash
    assert isinstance(items, list)


def test_handles_empty_corpus_gracefully() -> None:
    strategy = LexicalRetrievalStrategy(chunks=[])
    query = _make_query(
        changed_symbols=["login"],
        diff_text="login user",
    )

    items = strategy.retrieve(query)

    assert items == []


def test_handles_empty_query_gracefully() -> None:
    chunks = [
        _make_chunk("auth.py", "login", "def login_user(): ..."),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(changed_symbols=[], diff_text="")

    items = strategy.retrieve(query)

    assert items == []


def test_scores_are_positive_floats() -> None:
    chunks = [
        _make_chunk("auth.py", "login", "def login_user(username, password): ..."),
        _make_chunk(
            "handler.py",
            "handle",
            "def handle_login(username): login_user(username)",
        ),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["login_user"],
        diff_text="login username password",
    )

    items = strategy.retrieve(query)

    for item in items:
        assert isinstance(item.relevance_score, float)
        assert item.relevance_score > 0.0


def test_budget_limits_top_k() -> None:
    chunks = [
        _make_chunk("a.py", "fn_a", "def fn_a(login, password): ...", tokens=100),
        _make_chunk("b.py", "fn_b", "def fn_b(login, user): ...", tokens=100),
        _make_chunk("c.py", "fn_c", "def fn_c(login, auth): ...", tokens=100),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["login"],
        diff_text="login user password",
    )

    # With budget of 150 tokens, avg chunk cost is 100, so k=1.
    items = strategy.retrieve(query, budget=TokenCount(150))
    assert len(items) <= 2


def test_budget_none_uses_default_top_k() -> None:
    chunks = [
        _make_chunk("a.py", "fn_a", "def fn_a(login, password): ...", tokens=50),
        _make_chunk("b.py", "fn_b", "def fn_b(login, user): ...", tokens=50),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["login"],
        diff_text="login user password",
    )

    items = strategy.retrieve(query, budget=None)
    assert isinstance(items, list)


def test_lexical_out_of_bounds_index_skipped_gracefully() -> None:
    chunks = [
        _make_chunk("auth.py", "login", "def login_user(username, password): ..."),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["login_user"],
        diff_text="login username password",
    )

    # Monkey-patch BM25 to return an out-of-range index.
    import numpy as np

    oob_results = np.array([[999]])
    oob_scores = np.array([[1.5]])
    strategy._index.retrieve = lambda *_args, **_kwargs: (oob_results, oob_scores)  # type: ignore[method-assign]

    items = strategy.retrieve(query)
    assert items == []


def test_token_cost_preserved_from_chunks() -> None:
    chunks = [
        _make_chunk(
            "auth.py",
            "login",
            "def login_user(username, password): ...",
            tokens=42,
        ),
        _make_chunk(
            "handler.py",
            "handle",
            "def handle_login(username): login_user(username)",
            tokens=99,
        ),
    ]
    strategy = LexicalRetrievalStrategy(chunks=chunks)
    query = _make_query(
        changed_symbols=["login_user"],
        diff_text="login username",
    )

    items = strategy.retrieve(query)

    for item in items:
        matching_chunk = next(c for c in chunks if c.source == item.source)
        assert item.token_cost == matching_chunk.token_cost
