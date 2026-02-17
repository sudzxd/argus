"""Tests for ReviewPullRequest use case."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from argus.application.dto import ReviewPullRequestCommand, ReviewPullRequestResult
from argus.application.review_pull_request import ReviewPullRequest
from argus.domain.context.entities import FileEntry
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


@pytest.fixture
def mock_review_generator() -> MagicMock:
    gen = MagicMock()
    gen.generate.return_value = _make_review(1)
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
    mock_review_generator.generate.return_value = review_with_noise
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
