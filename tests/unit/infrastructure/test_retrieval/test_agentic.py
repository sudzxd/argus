"""Tests for agentic (LLM-guided tool-based) retrieval strategy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from argus.domain.llm.value_objects import LLMUsage, ModelConfig
from argus.domain.retrieval.value_objects import RetrievalQuery
from argus.infrastructure.parsing.chunker import CodeChunk
from argus.infrastructure.retrieval.agentic import (
    AgenticRetrievalStrategy,
    ExplorationResult,
    RelevantFile,
    _AgenticDeps,
    fetch_file,
    search_code,
)
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# Helpers
# =============================================================================


def _make_config() -> ModelConfig:
    return ModelConfig(
        model="test",
        max_tokens=TokenCount(4096),
    )


def _make_query(
    changed_files: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    diff_text: str = "def foo(): pass",
) -> RetrievalQuery:
    return RetrievalQuery(
        changed_files=tuple(FilePath(f) for f in (changed_files or [])),
        changed_symbols=tuple(changed_symbols or []),
        diff_text=diff_text,
    )


def _make_chunk(
    source: str = "lib.py",
    symbol_name: str = "helper",
    content: str = "def helper(): return 42",
    tokens: int = 10,
) -> CodeChunk:
    return CodeChunk(
        source=FilePath(source),
        symbol_name=symbol_name,
        content=content,
        token_cost=TokenCount(tokens),
    )


def _make_deps(
    chunks: list[CodeChunk] | None = None,
    changed_files: set[FilePath] | None = None,
    max_fetches: int = 10,
    max_file_chars: int = 15_000,
) -> _AgenticDeps:
    client = MagicMock()
    return _AgenticDeps(
        client=client,
        ref="abc123",
        chunks=chunks or [],
        changed_files=changed_files or set(),
        max_fetches=max_fetches,
        max_file_chars=max_file_chars,
    )


def _make_run_context(deps: _AgenticDeps) -> MagicMock:
    """Create a mock RunContext wrapping the given deps."""
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _make_mock_run_result(
    exploration: ExplorationResult,
    input_tokens: int = 100,
    output_tokens: int = 50,
    requests: int = 1,
) -> MagicMock:
    """Create a mock agent run result."""
    mock_result = MagicMock()
    mock_result.output = exploration
    mock_usage = MagicMock()
    mock_usage.input_tokens = input_tokens
    mock_usage.output_tokens = output_tokens
    mock_usage.requests = requests
    mock_result.usage.return_value = mock_usage
    return mock_result


# =============================================================================
# fetch_file tool tests
# =============================================================================


def test_fetch_file_tool_returns_content() -> None:
    deps = _make_deps()
    deps.client.get_file_content.return_value = "def hello(): pass"
    ctx = _make_run_context(deps)

    result = fetch_file(ctx, "src/hello.py")

    assert result == "def hello(): pass"
    deps.client.get_file_content.assert_called_once_with(
        FilePath("src/hello.py"), ref="abc123"
    )
    assert deps.fetch_count == 1
    assert "src/hello.py" in deps.fetched_files


def test_fetch_file_tool_enforces_limit() -> None:
    deps = _make_deps(max_fetches=2)
    deps.client.get_file_content.return_value = "content"
    ctx = _make_run_context(deps)

    fetch_file(ctx, "a.py")
    fetch_file(ctx, "b.py")
    result = fetch_file(ctx, "c.py")

    assert "Error: fetch limit reached" in result
    assert deps.fetch_count == 2
    assert "c.py" not in deps.fetched_files


def test_fetch_file_tool_truncates_large_files() -> None:
    deps = _make_deps(max_file_chars=100)
    large_content = "x" * 200
    deps.client.get_file_content.return_value = large_content
    ctx = _make_run_context(deps)

    result = fetch_file(ctx, "big.py")

    assert len(result) < 200
    assert result.endswith("... [truncated]")
    assert deps.fetched_files["big.py"].endswith("... [truncated]")


def test_fetch_file_tool_handles_api_error() -> None:
    deps = _make_deps()
    deps.client.get_file_content.side_effect = RuntimeError("API error")
    ctx = _make_run_context(deps)

    result = fetch_file(ctx, "missing.py")

    assert "Error fetching missing.py" in result
    assert deps.fetch_count == 0
    assert "missing.py" not in deps.fetched_files


def test_fetch_file_tool_returns_cached_on_repeat() -> None:
    deps = _make_deps()
    deps.client.get_file_content.return_value = "def hello(): pass"
    ctx = _make_run_context(deps)

    fetch_file(ctx, "src/hello.py")
    result = fetch_file(ctx, "src/hello.py")

    assert result == "def hello(): pass"
    assert deps.fetch_count == 1  # Only one actual fetch
    deps.client.get_file_content.assert_called_once()


# =============================================================================
# search_code tool tests
# =============================================================================


def test_search_code_tool_returns_matching_chunks() -> None:
    chunks = [
        _make_chunk(
            source="utils.py",
            symbol_name="parse",
            content="def parse(x): return x",
        ),
        _make_chunk(
            source="main.py",
            symbol_name="run",
            content="def run(): start()",
        ),
    ]
    deps = _make_deps(chunks=chunks)
    ctx = _make_run_context(deps)

    result = search_code(ctx, "parse")

    assert "utils.py" in result
    assert "parse" in result


def test_search_code_tool_excludes_changed_files() -> None:
    chunks = [
        _make_chunk(
            source="changed.py",
            symbol_name="fn",
            content="def fn(): pass",
        ),
        _make_chunk(
            source="other.py",
            symbol_name="fn2",
            content="def fn2(): return fn()",
        ),
    ]
    deps = _make_deps(
        chunks=chunks,
        changed_files={FilePath("changed.py")},
    )
    ctx = _make_run_context(deps)

    result = search_code(ctx, "fn")

    assert "changed.py" not in result


def test_search_code_tool_empty_chunks() -> None:
    deps = _make_deps(chunks=[])
    ctx = _make_run_context(deps)

    result = search_code(ctx, "anything")

    assert result == "No code chunks available for search."


# =============================================================================
# Strategy retrieve tests
# =============================================================================


def test_retrieve_converts_exploration_to_context_items() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    exploration = ExplorationResult(
        relevant_files=[
            RelevantFile(path="lib.py", relevance_score=0.9, reason="dependency"),
        ]
    )

    mock_result = _make_mock_run_result(exploration)

    def fake_run_sync(prompt: str, *, deps: _AgenticDeps) -> MagicMock:
        deps.fetched_files["lib.py"] = "def helper(): return 42"
        return mock_result

    with patch.object(strategy._agent, "run_sync", side_effect=fake_run_sync):
        items = strategy.retrieve(_make_query())

    assert len(items) == 1
    assert items[0].source == FilePath("lib.py")
    assert items[0].relevance_score == 0.9
    assert items[0].content == "def helper(): return 42"


def test_retrieve_skips_unfetched_files() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    exploration = ExplorationResult(
        relevant_files=[
            RelevantFile(path="fetched.py", relevance_score=0.9, reason="found it"),
            RelevantFile(path="not_fetched.py", relevance_score=0.8, reason="claimed"),
        ]
    )

    mock_result = _make_mock_run_result(exploration)

    def fake_run_sync(prompt: str, *, deps: _AgenticDeps) -> MagicMock:
        deps.fetched_files["fetched.py"] = "content of fetched"
        return mock_result

    with patch.object(strategy._agent, "run_sync", side_effect=fake_run_sync):
        items = strategy.retrieve(_make_query())

    sources = {item.source for item in items}
    assert FilePath("fetched.py") in sources
    assert FilePath("not_fetched.py") not in sources


def test_retrieve_respects_budget() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    exploration = ExplorationResult(
        relevant_files=[
            RelevantFile(path="a.py", relevance_score=0.9, reason="high"),
            RelevantFile(path="b.py", relevance_score=0.8, reason="medium"),
        ]
    )

    # Each file is 400 chars = 100 tokens (400 / CHARS_PER_TOKEN=4)
    file_content = "x" * 400
    mock_result = _make_mock_run_result(exploration)

    def fake_run_sync(prompt: str, *, deps: _AgenticDeps) -> MagicMock:
        deps.fetched_files["a.py"] = file_content
        deps.fetched_files["b.py"] = file_content
        return mock_result

    with patch.object(strategy._agent, "run_sync", side_effect=fake_run_sync):
        items = strategy.retrieve(_make_query(), budget=TokenCount(150))

    # Budget is 150, each item costs 100 tokens — should get at most 1
    assert len(items) == 1
    assert items[0].source == FilePath("a.py")


def test_retrieve_tracks_llm_usage() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    exploration = ExplorationResult(relevant_files=[])
    mock_result = _make_mock_run_result(
        exploration, input_tokens=200, output_tokens=80, requests=3
    )

    with patch.object(strategy._agent, "run_sync", return_value=mock_result):
        strategy.retrieve(_make_query())

    assert isinstance(strategy.last_llm_usage, LLMUsage)
    assert strategy.last_llm_usage.input_tokens == 200
    assert strategy.last_llm_usage.output_tokens == 80
    assert strategy.last_llm_usage.requests == 3


def test_retrieve_resets_usage_between_calls() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    exploration = ExplorationResult(relevant_files=[])
    mock_result = _make_mock_run_result(
        exploration, input_tokens=500, output_tokens=100, requests=2
    )

    with patch.object(strategy._agent, "run_sync", return_value=mock_result):
        strategy.retrieve(_make_query())
        first_usage = strategy.last_llm_usage

        strategy.retrieve(_make_query())
        second_usage = strategy.last_llm_usage

    assert first_usage.input_tokens == 500
    assert second_usage.input_tokens == 500


def test_retrieve_with_outline_in_system_prompt() -> None:
    outline = "# src/lib.py\n  def helper(x: int) -> str\n"
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
        outline_text=outline,
    )

    assert outline in strategy._agent._system_prompts[0]


def test_retrieve_without_outline() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
        outline_text=None,
    )

    # The appended outline section should NOT appear when outline_text is None
    assert "Below is the codebase outline" not in strategy._agent._system_prompts[0]


def test_retrieve_excludes_changed_files_from_results() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    exploration = ExplorationResult(
        relevant_files=[
            RelevantFile(path="changed.py", relevance_score=0.9, reason="changed"),
            RelevantFile(path="other.py", relevance_score=0.8, reason="related"),
        ]
    )

    mock_result = _make_mock_run_result(exploration)

    def fake_run_sync(prompt: str, *, deps: _AgenticDeps) -> MagicMock:
        deps.fetched_files["changed.py"] = "changed content"
        deps.fetched_files["other.py"] = "other content"
        return mock_result

    with patch.object(strategy._agent, "run_sync", side_effect=fake_run_sync):
        items = strategy.retrieve(_make_query(changed_files=["changed.py"]))

    sources = {item.source for item in items}
    assert FilePath("changed.py") not in sources
    assert FilePath("other.py") in sources


def test_retrieve_handles_agent_failure_gracefully() -> None:
    strategy = AgenticRetrievalStrategy(
        config=_make_config(),
        client=MagicMock(),
        ref="abc123",
        chunks=[],
    )

    with patch.object(
        strategy._agent, "run_sync", side_effect=RuntimeError("LLM failed")
    ):
        items = strategy.retrieve(_make_query())

    assert items == []
    assert strategy.last_llm_usage == LLMUsage()
