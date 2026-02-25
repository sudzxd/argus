"""Agentic retrieval — LLM-guided codebase exploration via pydantic-ai tools."""

from __future__ import annotations

import logging

from dataclasses import dataclass, field

import bm25s

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from argus.domain.llm.value_objects import LLMUsage, ModelConfig
from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.infrastructure.constants import CHARS_PER_TOKEN
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.parsing.chunker import CodeChunk
from argus.shared.constants import (
    AGENTIC_SEARCH_RESULTS,
    MAX_AGENTIC_FILE_CHARS,
    MAX_AGENTIC_FILE_FETCHES,
    MAX_AGENTIC_ITERATIONS,
)
from argus.shared.types import FilePath, TokenCount

logger = logging.getLogger(__name__)

# =============================================================================
# TOOL DEPENDENCIES
# =============================================================================


@dataclass
class _AgenticDeps:
    """Dependencies injected into agent tools at runtime."""

    client: GitHubClient
    ref: str
    chunks: list[CodeChunk]
    changed_files: set[FilePath]
    fetched_files: dict[str, str] = field(default_factory=dict[str, str])
    fetch_count: int = 0
    max_fetches: int = MAX_AGENTIC_FILE_FETCHES
    max_file_chars: int = MAX_AGENTIC_FILE_CHARS
    _bm25_index: bm25s.BM25 | None = field(init=False, default=None)
    _bm25_built: bool = field(init=False, default=False)

    def get_bm25_index(self) -> bm25s.BM25 | None:
        """Build and cache BM25 index over chunks on first access."""
        if self._bm25_built:
            return self._bm25_index
        self._bm25_built = True
        if not self.chunks:
            return None
        self._bm25_index = bm25s.BM25()
        corpus = [chunk.content for chunk in self.chunks]
        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", show_progress=False)
        self._bm25_index.index(corpus_tokens, show_progress=False)
        return self._bm25_index


# =============================================================================
# STRUCTURED OUTPUT
# =============================================================================


class RelevantFile(BaseModel):
    """A file the agent identified as relevant."""

    path: str
    relevance_score: float
    reason: str


class ExplorationResult(BaseModel):
    """Structured output from the exploration agent."""

    relevant_files: list[RelevantFile]


# =============================================================================
# TOOLS
# =============================================================================


def fetch_file(ctx: RunContext[_AgenticDeps], path: str) -> str:
    """Fetch and read a file's contents from the repository.

    Args:
        ctx: Run context with dependencies.
        path: File path to read (e.g. 'src/utils.py').

    Returns:
        File content (possibly truncated) or error message.
    """
    deps = ctx.deps

    if deps.fetch_count >= deps.max_fetches:
        return (
            f"Error: fetch limit reached ({deps.max_fetches} files). "
            "Use search_code instead."
        )

    if path in deps.fetched_files:
        return deps.fetched_files[path]

    try:
        content = deps.client.get_file_content(FilePath(path), ref=deps.ref)
    except Exception as e:
        return f"Error fetching {path}: {e}"

    if len(content) > deps.max_file_chars:
        content = content[: deps.max_file_chars] + "\n... [truncated]"

    deps.fetched_files[path] = content
    deps.fetch_count += 1
    return content


def search_code(ctx: RunContext[_AgenticDeps], query: str) -> str:
    """Search the codebase for code matching keywords via BM25.

    Args:
        ctx: Run context with dependencies.
        query: Search query keywords.

    Returns:
        Formatted search results with file paths and code snippets.
    """
    deps = ctx.deps
    index = deps.get_bm25_index()

    if index is None:
        return "No code chunks available for search."

    query_tokens = bm25s.tokenize([query], stopwords="en", show_progress=False)
    k = min(AGENTIC_SEARCH_RESULTS * 2, len(deps.chunks))
    results, scores = index.retrieve(query_tokens, k=k, show_progress=False)

    output_parts: list[str] = []
    count = 0
    for idx, score in zip(results[0], scores[0], strict=True):
        score_val = float(score)
        if score_val <= 0.0:
            continue
        chunk_idx = int(idx)
        if chunk_idx < 0 or chunk_idx >= len(deps.chunks):
            continue
        chunk = deps.chunks[chunk_idx]
        if chunk.source in deps.changed_files:
            continue

        snippet = chunk.content[:500]
        if len(chunk.content) > 500:
            snippet += "\n..."
        output_parts.append(
            f"## {chunk.source} ({chunk.symbol_name})\n```\n{snippet}\n```"
        )
        count += 1
        if count >= AGENTIC_SEARCH_RESULTS:
            break

    if not output_parts:
        return "No results found."

    return "\n\n".join(output_parts)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

_BASE_SYSTEM_PROMPT = """\
You are a code exploration agent helping review a pull request. Your job is to \
find files in the repository that are relevant to understanding the changes.

You have two tools:
- `fetch_file(path)`: Read a file's contents from the repository.
- `search_code(query)`: Search the codebase using keyword queries (BM25).

Your approach:
1. Study the diff to understand what changed.
2. Use `search_code` to find code matching specific symbols, function names, \
or concepts from the diff.
3. Use `fetch_file` to read promising files identified by search or the \
codebase outline.
4. Focus on:
   - Dependencies of changed code (imports, called functions)
   - Similar or duplicate implementations
   - Callers of changed APIs
   - Files that might be affected by the changes
5. Score each relevant file 0.0-1.0 based on how important it is for \
reviewing the diff.
6. Only include files you've actually examined via fetch_file or search_code.
"""


# =============================================================================
# STRATEGY
# =============================================================================


@dataclass
class AgenticRetrievalStrategy:
    """LLM-guided codebase exploration with tools.

    Uses a pydantic-ai Agent with fetch_file and search_code tools to
    explore the codebase and identify files relevant to the PR diff.
    """

    config: ModelConfig
    client: GitHubClient
    ref: str
    chunks: list[CodeChunk]
    outline_text: str | None = None
    max_file_fetches: int = MAX_AGENTIC_FILE_FETCHES
    _agent: Agent[_AgenticDeps, ExplorationResult] = field(init=False, repr=False)
    last_llm_usage: LLMUsage = field(init=False, default_factory=LLMUsage)

    def __post_init__(self) -> None:
        system_prompt = _BASE_SYSTEM_PROMPT
        if self.outline_text:
            system_prompt += (
                "\n\nBelow is the codebase outline showing all files and "
                "their symbols. Use this to identify which files to explore:"
                f"\n\n{self.outline_text}"
            )

        self._agent = Agent(
            model=self.config.model,
            deps_type=_AgenticDeps,
            output_type=ExplorationResult,
            system_prompt=system_prompt,
            tools=[fetch_file, search_code],
            model_settings={
                "max_tokens": int(self.config.max_tokens),
                "temperature": self.config.temperature,
            },
            retries=MAX_AGENTIC_ITERATIONS,
        )

    def retrieve(
        self, query: RetrievalQuery, budget: TokenCount | None = None
    ) -> list[ContextItem]:
        """Explore the codebase and retrieve relevant context items."""
        changed = set(query.changed_files)
        self.last_llm_usage = LLMUsage()

        deps = _AgenticDeps(
            client=self.client,
            ref=self.ref,
            chunks=self.chunks,
            changed_files=changed,
            max_fetches=self.max_file_fetches,
        )

        user_prompt = self._build_prompt(query)

        try:
            result = self._agent.run_sync(user_prompt, deps=deps)
        except Exception:
            logger.warning("Agentic retrieval failed, returning empty results")
            return []

        run_usage = result.usage()
        self.last_llm_usage = LLMUsage(
            input_tokens=run_usage.input_tokens or 0,
            output_tokens=run_usage.output_tokens or 0,
            requests=run_usage.requests,
        )

        return self._build_context_items(
            result.output, deps.fetched_files, changed, budget
        )

    def _build_prompt(self, query: RetrievalQuery) -> str:
        """Build the user prompt from the retrieval query."""
        parts = [f"## Diff\n```\n{query.diff_text}\n```"]
        if query.changed_symbols:
            parts.append(f"## Changed symbols\n{', '.join(query.changed_symbols)}")
        parts.append(
            "Explore the codebase to find files relevant to reviewing this diff."
        )
        return "\n\n".join(parts)

    def _build_context_items(
        self,
        exploration: ExplorationResult,
        fetched_files: dict[str, str],
        changed: set[FilePath],
        budget: TokenCount | None,
    ) -> list[ContextItem]:
        """Convert exploration results to context items."""
        items: list[ContextItem] = []
        accumulated_tokens = 0

        sorted_files = sorted(
            exploration.relevant_files,
            key=lambda f: f.relevance_score,
            reverse=True,
        )

        for relevant_file in sorted_files:
            path = FilePath(relevant_file.path)
            if path in changed:
                continue

            content = fetched_files.get(relevant_file.path)
            if content is None:
                continue

            token_cost = TokenCount(max(1, len(content) // CHARS_PER_TOKEN))

            if budget is not None and accumulated_tokens + int(token_cost) > int(
                budget
            ):
                break

            items.append(
                ContextItem(
                    source=path,
                    content=content,
                    relevance_score=relevant_file.relevance_score,
                    token_cost=token_cost,
                )
            )
            accumulated_tokens += int(token_cost)

        return items
