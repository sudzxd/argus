"""Tests for the symbol-boundary code chunker."""

from __future__ import annotations

from argus.domain.context.value_objects import Symbol, SymbolKind
from argus.infrastructure.constants import MODULE_CHUNK_NAME
from argus.infrastructure.parsing.chunker import Chunker, CodeChunk
from argus.shared.types import FilePath, LineRange, TokenCount

# =============================================================================
# Fixtures
# =============================================================================


def _make_symbol(name: str, start: int, end: int) -> Symbol:
    return Symbol(
        name=name,
        kind=SymbolKind.FUNCTION,
        line_range=LineRange(start=start, end=end),
    )


# =============================================================================
# Tests
# =============================================================================


def test_chunk_returns_code_chunks() -> None:
    chunker = Chunker()
    code = "def hello():\n    return 1\n"
    symbols = [_make_symbol("hello", 1, 2)]

    chunks = chunker.chunk(FilePath("test.py"), code, symbols)

    assert len(chunks) == 1
    assert isinstance(chunks[0], CodeChunk)


def test_chunk_splits_at_symbol_boundaries() -> None:
    chunker = Chunker()
    code = "def first():\n    pass\n\ndef second():\n    pass\n"
    symbols = [
        _make_symbol("first", 1, 2),
        _make_symbol("second", 4, 5),
    ]

    chunks = chunker.chunk(FilePath("funcs.py"), code, symbols)

    assert len(chunks) == 2
    assert chunks[0].symbol_name == "first"
    assert chunks[1].symbol_name == "second"
    assert "first" in chunks[0].content
    assert "second" in chunks[1].content


def test_chunk_no_symbols_returns_whole_file() -> None:
    chunker = Chunker()
    code = "# just a comment\nx = 1\n"

    chunks = chunker.chunk(FilePath("config.py"), code, [])

    assert len(chunks) == 1
    assert chunks[0].symbol_name == MODULE_CHUNK_NAME
    assert chunks[0].content == code


def test_chunk_token_cost_is_positive() -> None:
    chunker = Chunker()
    code = "def hello():\n    return 1\n"
    symbols = [_make_symbol("hello", 1, 2)]

    chunks = chunker.chunk(FilePath("test.py"), code, symbols)

    assert chunks[0].token_cost >= TokenCount(1)


def test_chunk_source_matches_file_path() -> None:
    chunker = Chunker()
    path = FilePath("src/module.py")
    code = "def func(): pass\n"
    symbols = [_make_symbol("func", 1, 1)]

    chunks = chunker.chunk(path, code, symbols)

    assert chunks[0].source == path
