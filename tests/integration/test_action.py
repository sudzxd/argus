"""Integration tests for the Argus action pipeline.

These tests wire real internal components (parser, chunker, storage,
retrieval, noise filter, publisher formatting) and mock only external
HTTP boundaries (GitHub API, LLM API).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from argus.application.dto import ReviewPullRequestCommand
from argus.application.review_pull_request import ReviewPullRequest
from argus.domain.context.services import IndexingService
from argus.domain.llm.value_objects import ModelConfig
from argus.domain.retrieval.services import RetrievalOrchestrator
from argus.domain.review.services import NoiseFilter
from argus.infrastructure.github.publisher import GitHubReviewPublisher
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.retrieval.lexical import LexicalRetrievalStrategy
from argus.infrastructure.storage.artifact_store import FileArtifactStore
from argus.interfaces.action import (
    _extract_changed_files,
    _extract_head_sha,
    _extract_pr_number,
    _load_event,
)
from argus.interfaces.review_generator import LLMReviewGenerator, ReviewOutput
from argus.shared.exceptions import ConfigurationError
from argus.shared.types import CommitSHA, FilePath, TokenCount


def _make_command(
    file_contents: dict[FilePath, str] | None = None,
) -> ReviewPullRequestCommand:
    contents = file_contents or {
        FilePath("src/auth.py"): (
            "import hashlib\n\n"
            "def login(user, password):\n"
            "    return check_password(user, password)\n"
        )
    }
    return ReviewPullRequestCommand(
        repo_id="owner/repo",
        pr_number=42,
        commit_sha=CommitSHA("abc123def456"),
        diff=(
            "diff --git a/src/auth.py b/src/auth.py\n"
            "--- a/src/auth.py\n"
            "+++ b/src/auth.py\n"
            "@@ -1,3 +1,5 @@\n"
            "+import hashlib\n"
            "+\n"
            " def login(user, password):\n"
            "     return check_password(user, password)\n"
        ),
        changed_files=list(contents.keys()),
        file_contents=contents,
    )


# =============================================================================
# EVENT PARSING TESTS
# =============================================================================


class TestEventParsing:
    """Test GitHub event JSON parsing helpers."""

    def test_load_event(self, github_event: Path) -> None:
        event = _load_event(str(github_event))
        assert "pull_request" in event

    def test_load_event_missing_file_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="Event file not found"):
            _load_event("/nonexistent/path/event.json")

    def test_load_event_invalid_json_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{")
        with pytest.raises(ConfigurationError, match="Invalid event JSON"):
            _load_event(str(bad_file))

    def test_extract_pr_number(self) -> None:
        event = {"pull_request": {"number": 42, "head": {"sha": "abc"}}}
        assert _extract_pr_number(event) == 42

    def test_extract_pr_number_missing_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="PR number"):
            _extract_pr_number({})

    def test_extract_head_sha(self) -> None:
        event = {"pull_request": {"number": 42, "head": {"sha": "abc123"}}}
        assert _extract_head_sha(event) == "abc123"

    def test_extract_head_sha_missing_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="head SHA"):
            _extract_head_sha({})

    def test_extract_changed_files(self, sample_diff: str) -> None:
        files = _extract_changed_files(sample_diff)
        assert files == [FilePath("src/auth.py")]

    def test_extract_changed_files_multiple(self) -> None:
        diff = "+++ b/a.py\n+++ b/b.py\n+++ b/c.py\n"
        files = _extract_changed_files(diff)
        assert len(files) == 3

    def test_extract_changed_files_rejects_path_traversal(self) -> None:
        diff = "+++ b/../../../etc/passwd\n+++ b/safe.py\n"
        files = _extract_changed_files(diff)
        assert files == [FilePath("safe.py")]

    def test_extract_changed_files_rejects_absolute_path(self) -> None:
        diff = "+++ b//etc/passwd\n+++ b/safe.py\n"
        files = _extract_changed_files(diff)
        assert files == [FilePath("safe.py")]


# =============================================================================
# FULL PIPELINE TESTS
# =============================================================================


class TestFullPipeline:
    """End-to-end pipeline tests with real internals, mocked externals."""

    @patch("argus.interfaces.review_generator.create_agent")
    def test_action_full_review_pipeline(
        self,
        mock_create_agent: MagicMock,
        tmp_path: Path,
        sample_review_output: ReviewOutput,
    ) -> None:
        """Happy path: full pipeline produces and publishes a review."""
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = sample_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        parser = TreeSitterParser()
        store = FileArtifactStore(storage_dir=tmp_path / "artifacts")
        mock_client = MagicMock()
        cmd = _make_command()
        publisher = GitHubReviewPublisher(client=mock_client, diff=cmd.diff)

        orchestrator = RetrievalOrchestrator(
            strategies=[LexicalRetrievalStrategy(chunks=[])],
            budget=TokenCount(50_000),
        )

        model_config = ModelConfig(
            model="anthropic:claude-sonnet-4-5-20250929",
            max_tokens=TokenCount(4096),
        )
        review_generator = LLMReviewGenerator(config=model_config)
        noise_filter = NoiseFilter(confidence_threshold=0.7)

        use_case = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=noise_filter,
            publisher=publisher,
        )

        result = use_case.execute(cmd)

        # Review was generated
        expected = "Added hashlib import for password hashing."
        assert result.review.summary.description == expected
        assert len(result.review.comments) == 2

        # Review was published
        mock_client.post_review.assert_called_once()
        call_kwargs = mock_client.post_review.call_args
        assert call_kwargs[1]["pr_number"] == 42

    @patch("argus.interfaces.review_generator.create_agent")
    def test_action_no_existing_artifact(
        self,
        mock_create_agent: MagicMock,
        tmp_path: Path,
        sample_review_output: ReviewOutput,
    ) -> None:
        """First run with no stored CodebaseMap — full index + review."""
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = sample_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        store = FileArtifactStore(storage_dir=tmp_path / "artifacts")
        assert store.load("owner/repo") is None

        parser = TreeSitterParser()
        publisher = GitHubReviewPublisher(client=MagicMock())
        orchestrator = RetrievalOrchestrator(
            strategies=[LexicalRetrievalStrategy(chunks=[])],
            budget=TokenCount(50_000),
        )
        review_generator = LLMReviewGenerator(
            config=ModelConfig(
                model="anthropic:claude-sonnet-4-5-20250929",
                max_tokens=TokenCount(4096),
            )
        )

        use_case = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=NoiseFilter(confidence_threshold=0.7),
            publisher=publisher,
        )

        cmd = _make_command()
        result = use_case.execute(cmd)

        # CodebaseMap was created and persisted
        assert store.load("owner/repo") is not None
        assert result.review is not None

    @patch("argus.interfaces.review_generator.create_agent")
    def test_action_incremental_with_existing_artifact(
        self,
        mock_create_agent: MagicMock,
        tmp_path: Path,
        sample_review_output: ReviewOutput,
    ) -> None:
        """CodebaseMap already exists — incremental update."""
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = sample_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        store = FileArtifactStore(storage_dir=tmp_path / "artifacts")
        parser = TreeSitterParser()
        cmd = _make_command()

        # First run — builds the map
        orchestrator = RetrievalOrchestrator(
            strategies=[LexicalRetrievalStrategy(chunks=[])],
            budget=TokenCount(50_000),
        )
        review_generator = LLMReviewGenerator(
            config=ModelConfig(
                model="anthropic:claude-sonnet-4-5-20250929",
                max_tokens=TokenCount(4096),
            )
        )
        use_case = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=NoiseFilter(confidence_threshold=0.7),
            publisher=GitHubReviewPublisher(client=MagicMock(), diff=cmd.diff),
        )

        use_case.execute(cmd)

        # Second run — existing map should be loaded
        mock_publisher = MagicMock()
        use_case2 = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=NoiseFilter(confidence_threshold=0.7),
            publisher=GitHubReviewPublisher(client=mock_publisher, diff=cmd.diff),
        )

        result = use_case2.execute(cmd)
        assert result.review is not None
        mock_publisher.post_review.assert_called_once()

    @patch("argus.interfaces.review_generator.create_agent")
    def test_action_graceful_degradation_on_llm_failure(
        self,
        mock_create_agent: MagicMock,
        tmp_path: Path,
    ) -> None:
        """LLM failure raises and is propagatable."""
        mock_agent = MagicMock()
        mock_agent.run_sync.side_effect = RuntimeError("LLM API down")
        mock_create_agent.return_value = mock_agent

        parser = TreeSitterParser()
        store = FileArtifactStore(storage_dir=tmp_path / "artifacts")
        orchestrator = RetrievalOrchestrator(
            strategies=[LexicalRetrievalStrategy(chunks=[])],
            budget=TokenCount(50_000),
        )
        review_generator = LLMReviewGenerator(
            config=ModelConfig(
                model="anthropic:claude-sonnet-4-5-20250929",
                max_tokens=TokenCount(4096),
            )
        )

        use_case = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=NoiseFilter(confidence_threshold=0.7),
            publisher=GitHubReviewPublisher(client=MagicMock()),
        )

        cmd = _make_command()
        with pytest.raises(RuntimeError, match="LLM API down"):
            use_case.execute(cmd)

    @patch("argus.interfaces.review_generator.create_agent")
    def test_action_filters_low_confidence_comments(
        self,
        mock_create_agent: MagicMock,
        tmp_path: Path,
        low_confidence_review_output: ReviewOutput,
    ) -> None:
        """Comments below confidence threshold are dropped."""
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = low_confidence_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        parser = TreeSitterParser()
        store = FileArtifactStore(storage_dir=tmp_path / "artifacts")
        mock_client = MagicMock()
        publisher = GitHubReviewPublisher(client=mock_client)
        orchestrator = RetrievalOrchestrator(
            strategies=[LexicalRetrievalStrategy(chunks=[])],
            budget=TokenCount(50_000),
        )
        review_generator = LLMReviewGenerator(
            config=ModelConfig(
                model="anthropic:claude-sonnet-4-5-20250929",
                max_tokens=TokenCount(4096),
            )
        )

        use_case = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=NoiseFilter(confidence_threshold=0.7),
            publisher=publisher,
        )

        cmd = _make_command()
        result = use_case.execute(cmd)

        # Only the high-confidence comment survives
        assert len(result.review.comments) == 1
        assert result.review.comments[0].confidence == 0.95

    @patch("argus.interfaces.review_generator.create_agent")
    def test_action_respects_ignored_paths(
        self,
        mock_create_agent: MagicMock,
        tmp_path: Path,
        ignored_path_review_output: ReviewOutput,
    ) -> None:
        """Comments on ignored paths are dropped."""
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = ignored_path_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        parser = TreeSitterParser()
        store = FileArtifactStore(storage_dir=tmp_path / "artifacts")
        mock_client = MagicMock()
        publisher = GitHubReviewPublisher(client=mock_client)
        orchestrator = RetrievalOrchestrator(
            strategies=[LexicalRetrievalStrategy(chunks=[])],
            budget=TokenCount(50_000),
        )
        review_generator = LLMReviewGenerator(
            config=ModelConfig(
                model="anthropic:claude-sonnet-4-5-20250929",
                max_tokens=TokenCount(4096),
            )
        )

        use_case = ReviewPullRequest(
            indexing_service=IndexingService(parser=parser, repository=store),
            repository=store,
            orchestrator=orchestrator,
            review_generator=review_generator,
            noise_filter=NoiseFilter(
                confidence_threshold=0.5,
                ignored_paths=[FilePath("vendor/")],
            ),
            publisher=publisher,
        )

        cmd = _make_command()
        result = use_case.execute(cmd)

        # Only the src/auth.py comment survives
        assert len(result.review.comments) == 1
        assert result.review.comments[0].file == FilePath("src/auth.py")
