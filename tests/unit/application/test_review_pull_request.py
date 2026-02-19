"""Tests for ReviewPullRequest use case."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from argus.application.dto import ReviewPullRequestCommand, ReviewPullRequestResult
from argus.application.review_pull_request import ReviewPullRequest
from argus.domain.context.entities import FileEntry
from argus.domain.llm.value_objects import LLMUsage
from argus.domain.retrieval.value_objects import (
    ContextItem,
    RetrievalQuery,
    RetrievalResult,
)
from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewSummary
from argus.shared.types import (
    Category,
    CommitSHA,
    FilePath,
    LineRange,
    ReviewDepth,
    Severity,
    TokenCount,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_file_entry(path: str, sha: str = "abc") -> FileEntry:
    return FileEntry(
        path=FilePath(path),
        symbols=[],
        imports=[],
        exports=["func"],
        last_indexed=CommitSHA(sha),
    )


def _make_review(n_comments: int = 1) -> Review:
    comments = [
        ReviewComment(
            file=FilePath("file.py"),
            line_range=LineRange(start=1, end=5),
            severity=Severity.WARNING,
            category=Category.BUG,
            body="Potential issue",
            confidence=0.9,
        )
        for _ in range(n_comments)
    ]
    return Review(
        summary=ReviewSummary(
            description="Review",
            risks=["risk"],
            strengths=["good"],
            verdict="approve",
        ),
        comments=comments,
    )


@pytest.fixture
def mock_indexing_service() -> MagicMock:
    service = MagicMock()
    # full_index returns a CodebaseMap with the parsed entries
    from argus.domain.context.entities import CodebaseMap

    def _full_index(
        repo_id: str,
        commit_sha: CommitSHA,
        file_contents: dict[FilePath, str],
    ) -> CodebaseMap:
        cmap = CodebaseMap(indexed_at=commit_sha)
        for path in file_contents:
            cmap.upsert(_make_file_entry(str(path), str(commit_sha)))
        return cmap

    service.full_index.side_effect = _full_index
    return service


@pytest.fixture
def mock_repository() -> MagicMock:
    repo = MagicMock()
    repo.load.return_value = None
    return repo


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    orch = MagicMock()
    orch.retrieve.return_value = RetrievalResult(
        items=[
            ContextItem(
                source=FilePath("related.py"),
                content="def related(): pass",
                relevance_score=0.9,
                token_cost=TokenCount(10),
            ),
        ]
    )
    return orch


@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.count_tokens.return_value = TokenCount(50)
    return llm


def _make_llm_usage(
    input_tokens: int = 1000,
    output_tokens: int = 200,
    requests: int = 1,
) -> LLMUsage:
    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        requests=requests,
    )


@pytest.fixture
def mock_review_generator() -> MagicMock:
    gen = MagicMock()
    gen.generate.return_value = (_make_review(1), _make_llm_usage())
    return gen


@pytest.fixture
def mock_noise_filter() -> MagicMock:
    filt = MagicMock()
    filt.filter.side_effect = lambda comments: comments
    return filt


@pytest.fixture
def mock_publisher() -> MagicMock:
    return MagicMock()


@pytest.fixture
def use_case(
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
    mock_orchestrator: MagicMock,
    mock_review_generator: MagicMock,
    mock_noise_filter: MagicMock,
    mock_publisher: MagicMock,
) -> ReviewPullRequest:
    return ReviewPullRequest(
        indexing_service=mock_indexing_service,
        repository=mock_repository,
        orchestrator=mock_orchestrator,
        review_generator=mock_review_generator,
        noise_filter=mock_noise_filter,
        publisher=mock_publisher,
    )


def _make_command(
    pr_number: int = 42,
    changed_files: list[str] | None = None,
) -> ReviewPullRequestCommand:
    files = changed_files or ["file.py"]
    return ReviewPullRequestCommand(
        repo_id="org/repo",
        pr_number=pr_number,
        commit_sha=CommitSHA("abc123"),
        diff="diff --git a/file.py",
        changed_files=[FilePath(f) for f in files],
        file_contents={FilePath(f): "x = 1" for f in files},
    )


# =============================================================================
# Happy path
# =============================================================================


def test_execute_returns_result(use_case: ReviewPullRequest) -> None:
    result = use_case.execute(_make_command())

    assert isinstance(result, ReviewPullRequestResult)
    assert result.review.summary.description == "Review"
    assert result.context_items_used == 1
    assert result.tokens_used == TokenCount(10)
    assert result.llm_usage.input_tokens == 1000
    assert result.llm_usage.output_tokens == 200
    assert result.llm_usage.requests == 1


def test_execute_indexes_changed_files(
    use_case: ReviewPullRequest,
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
) -> None:
    use_case.execute(_make_command(changed_files=["a.py", "b.py"]))

    mock_indexing_service.full_index.assert_called_once()


def test_execute_calls_retrieval_orchestrator(
    use_case: ReviewPullRequest,
    mock_orchestrator: MagicMock,
) -> None:
    use_case.execute(_make_command())

    mock_orchestrator.retrieve.assert_called_once()
    query = mock_orchestrator.retrieve.call_args[0][0]
    assert isinstance(query, RetrievalQuery)
    assert FilePath("file.py") in query.changed_files


def test_execute_calls_review_generator(
    use_case: ReviewPullRequest,
    mock_review_generator: MagicMock,
) -> None:
    use_case.execute(_make_command())

    mock_review_generator.generate.assert_called_once()


def test_execute_applies_noise_filter(
    use_case: ReviewPullRequest,
    mock_noise_filter: MagicMock,
) -> None:
    use_case.execute(_make_command())

    mock_noise_filter.filter.assert_called_once()


def test_execute_publishes_review(
    use_case: ReviewPullRequest,
    mock_publisher: MagicMock,
) -> None:
    use_case.execute(_make_command())

    mock_publisher.publish.assert_called_once()
    published_review = mock_publisher.publish.call_args[0][0]
    assert isinstance(published_review, Review)
    pr_number = mock_publisher.publish.call_args[0][1]
    assert pr_number == 42


# =============================================================================
# Noise filtering
# =============================================================================


def test_filtered_comments_appear_in_published_review(
    use_case: ReviewPullRequest,
    mock_noise_filter: MagicMock,
    mock_publisher: MagicMock,
    mock_review_generator: MagicMock,
) -> None:
    review_with_noise = _make_review(3)
    mock_review_generator.generate.return_value = (review_with_noise, _make_llm_usage())
    mock_noise_filter.filter.side_effect = None
    mock_noise_filter.filter.return_value = review_with_noise.comments[:1]

    use_case.execute(_make_command())

    published_review = mock_publisher.publish.call_args[0][0]
    assert len(published_review.comments) == 1


# =============================================================================
# Edge cases
# =============================================================================


def test_execute_with_no_context_items(
    use_case: ReviewPullRequest,
    mock_orchestrator: MagicMock,
) -> None:
    mock_orchestrator.retrieve.return_value = RetrievalResult(items=[])

    result = use_case.execute(_make_command())

    assert result.context_items_used == 0
    assert result.tokens_used == TokenCount(0)


# =============================================================================
# Memory context
# =============================================================================


def test_execute_with_outline_renderer(
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
    mock_orchestrator: MagicMock,
    mock_review_generator: MagicMock,
    mock_noise_filter: MagicMock,
    mock_publisher: MagicMock,
) -> None:
    from argus.domain.memory.value_objects import CodebaseOutline, FileOutlineEntry

    mock_outline_renderer = MagicMock()
    mock_outline_renderer.render.return_value = (
        "# main.py\n  function main",
        CodebaseOutline(
            entries=[FileOutlineEntry(path=FilePath("main.py"), symbols=["main"])]
        ),
    )

    uc = ReviewPullRequest(
        indexing_service=mock_indexing_service,
        repository=mock_repository,
        orchestrator=mock_orchestrator,
        review_generator=mock_review_generator,
        noise_filter=mock_noise_filter,
        publisher=mock_publisher,
        outline_renderer=mock_outline_renderer,
    )

    cmd = ReviewPullRequestCommand(
        repo_id="org/repo",
        pr_number=42,
        commit_sha=CommitSHA("abc123"),
        diff="diff",
        changed_files=[FilePath("file.py")],
        file_contents={FilePath("file.py"): "x = 1"},
        review_depth=ReviewDepth.STANDARD,
    )
    uc.execute(cmd)

    # The outline text should be passed through to the review request.
    call_args = mock_review_generator.generate.call_args[0][0]
    assert call_args.codebase_outline_text is not None
    assert "main.py" in call_args.codebase_outline_text


def test_execute_quick_depth_skips_memory(
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
    mock_orchestrator: MagicMock,
    mock_review_generator: MagicMock,
    mock_noise_filter: MagicMock,
    mock_publisher: MagicMock,
) -> None:
    mock_outline_renderer = MagicMock()

    uc = ReviewPullRequest(
        indexing_service=mock_indexing_service,
        repository=mock_repository,
        orchestrator=mock_orchestrator,
        review_generator=mock_review_generator,
        noise_filter=mock_noise_filter,
        publisher=mock_publisher,
        outline_renderer=mock_outline_renderer,
    )

    cmd = ReviewPullRequestCommand(
        repo_id="org/repo",
        pr_number=42,
        commit_sha=CommitSHA("abc123"),
        diff="diff",
        changed_files=[FilePath("file.py")],
        file_contents={FilePath("file.py"): "x = 1"},
        review_depth=ReviewDepth.QUICK,
    )
    uc.execute(cmd)

    # Outline renderer should NOT be called for quick depth.
    mock_outline_renderer.render.assert_not_called()
    call_args = mock_review_generator.generate.call_args[0][0]
    assert call_args.codebase_outline_text is None


def test_execute_deep_depth_includes_patterns(
    mock_indexing_service: MagicMock,
    mock_repository: MagicMock,
    mock_orchestrator: MagicMock,
    mock_review_generator: MagicMock,
    mock_noise_filter: MagicMock,
    mock_publisher: MagicMock,
) -> None:
    from argus.domain.memory.value_objects import (
        CodebaseMemory,
        CodebaseOutline,
        FileOutlineEntry,
        PatternCategory,
        PatternEntry,
    )

    mock_outline_renderer = MagicMock()
    outline = CodebaseOutline(
        entries=[FileOutlineEntry(path=FilePath("main.py"), symbols=["main"])]
    )
    mock_outline_renderer.render.return_value = ("# outline text", outline)

    mock_memory_repo = MagicMock()
    mock_memory_repo.load.return_value = None

    mock_profile_service = MagicMock()
    mock_profile_service.build_profile.return_value = CodebaseMemory(
        repo_id="org/repo",
        outline=outline,
        patterns=[
            PatternEntry(
                category=PatternCategory.STYLE,
                description="Use snake_case",
                confidence=0.9,
            ),
        ],
        version=1,
    )

    uc = ReviewPullRequest(
        indexing_service=mock_indexing_service,
        repository=mock_repository,
        orchestrator=mock_orchestrator,
        review_generator=mock_review_generator,
        noise_filter=mock_noise_filter,
        publisher=mock_publisher,
        outline_renderer=mock_outline_renderer,
        memory_repository=mock_memory_repo,
        profile_service=mock_profile_service,
    )

    cmd = ReviewPullRequestCommand(
        repo_id="org/repo",
        pr_number=42,
        commit_sha=CommitSHA("abc123"),
        diff="diff",
        changed_files=[FilePath("file.py")],
        file_contents={FilePath("file.py"): "x = 1"},
        review_depth=ReviewDepth.DEEP,
    )
    uc.execute(cmd)

    call_args = mock_review_generator.generate.call_args[0][0]
    assert call_args.codebase_outline_text is not None
    assert call_args.codebase_patterns_text is not None
    assert "snake_case" in call_args.codebase_patterns_text
