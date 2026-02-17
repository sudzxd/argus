"""Tests for LLMReviewGenerator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argus.domain.llm.value_objects import ModelConfig
from argus.domain.retrieval.value_objects import ContextItem, RetrievalResult
from argus.domain.review.value_objects import ReviewRequest
from argus.interfaces.review_generator import (
    LLMReviewGenerator,
    ReviewOutput,
)
from argus.shared.types import (
    Category,
    FilePath,
    LineRange,
    Severity,
    TokenCount,
)


@pytest.fixture
def model_config() -> ModelConfig:
    return ModelConfig(
        model="anthropic:claude-sonnet-4-5-20250929",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )


@pytest.fixture
def review_request() -> ReviewRequest:
    return ReviewRequest(
        diff_text="--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,4 @@\n+import os\n",
        context=RetrievalResult(
            items=[
                ContextItem(
                    source=FilePath("bar.py"),
                    content="def helper(): ...",
                    relevance_score=0.9,
                    token_cost=TokenCount(10),
                ),
            ]
        ),
    )


@pytest.fixture
def sample_review_output() -> ReviewOutput:
    return ReviewOutput(
        summary_description="Good changes overall.",
        summary_risks=["Unused import"],
        summary_strengths=["Clean structure"],
        summary_verdict="Approve with suggestions",
        comments=[
            ReviewOutput.CommentOutput(
                file="foo.py",
                line_start=1,
                line_end=1,
                severity="suggestion",
                category="style",
                body="Unused import 'os'",
                confidence=0.85,
                suggestion="Remove the unused import.",
            )
        ],
    )


class TestLLMReviewGenerator:
    """Test the LLM review generator bridge."""

    @patch("argus.interfaces.review_generator.create_agent")
    def test_generate_returns_review(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
        review_request: ReviewRequest,
        sample_review_output: ReviewOutput,
    ) -> None:
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = sample_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        generator = LLMReviewGenerator(config=model_config)
        review = generator.generate(review_request)

        assert review.summary.description == "Good changes overall."
        assert review.summary.risks == ["Unused import"]
        assert review.summary.strengths == ["Clean structure"]
        assert review.summary.verdict == "Approve with suggestions"
        assert len(review.comments) == 1

        comment = review.comments[0]
        assert comment.file == FilePath("foo.py")
        assert comment.line_range == LineRange(1, 1)
        assert comment.severity == Severity.SUGGESTION
        assert comment.category == Category.STYLE
        assert comment.body == "Unused import 'os'"
        assert comment.confidence == 0.85
        assert comment.suggestion == "Remove the unused import."

    @patch("argus.interfaces.review_generator.create_agent")
    def test_generate_with_no_comments(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
        review_request: ReviewRequest,
    ) -> None:
        output = ReviewOutput(
            summary_description="LGTM",
            summary_risks=[],
            summary_strengths=["Solid code"],
            summary_verdict="Approve",
            comments=[],
        )
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        generator = LLMReviewGenerator(config=model_config)
        review = generator.generate(review_request)

        assert len(review.comments) == 0
        assert review.summary.verdict == "Approve"

    @patch("argus.interfaces.review_generator.create_agent")
    def test_generate_maps_all_severities(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
        review_request: ReviewRequest,
    ) -> None:
        comments = [
            ReviewOutput.CommentOutput(
                file="a.py",
                line_start=1,
                line_end=1,
                severity=sev,
                category="bug",
                body=f"Issue at {sev}",
                confidence=0.9,
                suggestion=None,
            )
            for sev in ("praise", "suggestion", "warning", "critical")
        ]
        output = ReviewOutput(
            summary_description="Mixed",
            summary_risks=[],
            summary_strengths=[],
            summary_verdict="Changes requested",
            comments=comments,
        )
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        generator = LLMReviewGenerator(config=model_config)
        review = generator.generate(review_request)

        severities = [c.severity for c in review.comments]
        assert severities == [
            Severity.PRAISE,
            Severity.SUGGESTION,
            Severity.WARNING,
            Severity.CRITICAL,
        ]

    @patch("argus.interfaces.review_generator.create_agent")
    def test_prompt_includes_diff_and_context(
        self,
        mock_create_agent: MagicMock,
        model_config: ModelConfig,
        review_request: ReviewRequest,
        sample_review_output: ReviewOutput,
    ) -> None:
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = sample_review_output
        mock_agent.run_sync.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        generator = LLMReviewGenerator(config=model_config)
        generator.generate(review_request)

        call_args = mock_agent.run_sync.call_args[0][0]
        assert "foo.py" in call_args
        assert "import os" in call_args
        assert "bar.py" in call_args
