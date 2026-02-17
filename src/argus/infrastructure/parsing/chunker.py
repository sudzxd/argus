"""Symbol-boundary code chunker for retrieval indexing."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.context.value_objects import Symbol
from argus.infrastructure.constants import CHARS_PER_TOKEN, MODULE_CHUNK_NAME
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# TYPES
# =============================================================================


@dataclass(frozen=True)
class CodeChunk:
    """A chunk of source code at a symbol boundary."""

    source: FilePath
    symbol_name: str
    content: str
    token_cost: TokenCount


# =============================================================================
# CHUNKER
# =============================================================================


@dataclass
class Chunker:
    """Splits source files into chunks at symbol boundaries."""

    def chunk(
        self,
        path: FilePath,
        content: str,
        symbols: list[Symbol],
    ) -> list[CodeChunk]:
        """Split a file into chunks based on symbol boundaries.

        Args:
            path: File path.
            content: Full file content.
            symbols: Extracted symbols with line ranges.

        Returns:
            List of code chunks, one per symbol. If no symbols, returns
            a single chunk for the whole file.
        """
        if not symbols:
            return [self._make_chunk(path, MODULE_CHUNK_NAME, content)]

        lines = content.splitlines(keepends=True)
        chunks: list[CodeChunk] = []

        for symbol in symbols:
            start = symbol.line_range.start - 1  # 0-indexed
            end = symbol.line_range.end  # exclusive
            chunk_lines = lines[start:end]
            chunk_content = "".join(chunk_lines)
            chunks.append(self._make_chunk(path, symbol.name, chunk_content))

        return chunks

    def _make_chunk(self, path: FilePath, name: str, content: str) -> CodeChunk:
        token_cost = TokenCount(max(1, len(content) // CHARS_PER_TOKEN))
        return CodeChunk(
            source=path,
            symbol_name=name,
            content=content,
            token_cost=token_cost,
        )
