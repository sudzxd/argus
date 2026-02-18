"""Live provider smoke tests — verify structured output works with real APIs.

These tests are SKIPPED by default. To run them:

    # Anthropic
    ANTHROPIC_API_KEY=sk-... uv run pytest tests/smoke -m anthropic

    # OpenAI
    OPENAI_API_KEY=sk-... uv run pytest tests/smoke -m openai

    # Google (Gemini)
    GOOGLE_API_KEY=... uv run pytest tests/smoke -m google

    # All available providers at once
    ANTHROPIC_API_KEY=sk-... OPENAI_API_KEY=sk-... uv run pytest tests/smoke
"""

from __future__ import annotations

import os

import pytest

from argus.domain.llm.value_objects import ModelConfig
from argus.infrastructure.llm_providers.factory import create_agent
from argus.interfaces.review_generator import (
    SYSTEM_PROMPT,
    LLMReviewGenerator,
    ReviewOutput,
)
from argus.shared.types import TokenCount

# =============================================================================
# Fixtures
# =============================================================================

SAMPLE_DIFF = """\
--- a/utils.py
+++ b/utils.py
@@ -10,6 +10,9 @@ def get_user(user_id):
     conn = sqlite3.connect("app.db")
-    cursor = conn.execute("SELECT * FROM users WHERE id = " + user_id)
+    cursor = conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
     return cursor.fetchone()
"""

has_anthropic = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
has_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
has_google = pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set",
)


def _assert_valid_review(output: ReviewOutput) -> None:
    """Shared assertions for any provider's review output."""
    assert output.summary_description, "summary_description should not be empty"
    assert output.summary_verdict, "summary_verdict should not be empty"
    assert isinstance(output.summary_risks, list)
    assert isinstance(output.summary_strengths, list)
    assert isinstance(output.comments, list)
    # The SQL injection diff should produce at least one comment
    assert len(output.comments) >= 1, (
        "Expected at least one comment for SQL injection diff"
    )
    for comment in output.comments:
        assert comment.file, "comment.file should not be empty"
        assert comment.line_start > 0
        assert comment.line_end >= comment.line_start
        assert comment.severity in ("praise", "suggestion", "warning", "critical")
        assert comment.category in (
            "style",
            "performance",
            "bug",
            "security",
            "architecture",
        )
        assert 0.0 <= comment.confidence <= 1.0


# =============================================================================
# Anthropic
# =============================================================================


@has_anthropic
@pytest.mark.anthropic
def test_anthropic_structured_review() -> None:
    """Anthropic returns valid structured ReviewOutput via tool calling."""
    config = ModelConfig(
        model="anthropic:claude-haiku-3-5-20241022",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )
    agent = create_agent(
        config=config, output_type=ReviewOutput, system_prompt=SYSTEM_PROMPT
    )
    result = agent.run_sync(f"## Diff\n```\n{SAMPLE_DIFF}\n```")
    _assert_valid_review(result.output)


@has_anthropic
@pytest.mark.anthropic
def test_anthropic_full_review_generator() -> None:
    """Full LLMReviewGenerator pipeline works with Anthropic."""
    from argus.domain.retrieval.value_objects import RetrievalResult
    from argus.domain.review.value_objects import ReviewRequest

    config = ModelConfig(
        model="anthropic:claude-haiku-3-5-20241022",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )
    generator = LLMReviewGenerator(config=config)
    request = ReviewRequest(
        diff_text=SAMPLE_DIFF,
        context=RetrievalResult(items=[]),
    )
    review = generator.generate(request)
    assert review.summary.description
    assert len(review.comments) >= 1


# =============================================================================
# OpenAI
# =============================================================================


@has_openai
@pytest.mark.openai
def test_openai_structured_review() -> None:
    """OpenAI returns valid structured ReviewOutput via tool calling."""
    config = ModelConfig(
        model="openai:gpt-4o-mini",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )
    agent = create_agent(
        config=config, output_type=ReviewOutput, system_prompt=SYSTEM_PROMPT
    )
    result = agent.run_sync(f"## Diff\n```\n{SAMPLE_DIFF}\n```")
    _assert_valid_review(result.output)


# =============================================================================
# Google (Gemini)
# =============================================================================


@has_google
@pytest.mark.google
def test_google_structured_review() -> None:
    """Google Gemini returns valid structured ReviewOutput via tool calling."""
    config = ModelConfig(
        model="google-gla:gemini-2.5-flash",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )
    agent = create_agent(
        config=config, output_type=ReviewOutput, system_prompt=SYSTEM_PROMPT
    )
    result = agent.run_sync(f"## Diff\n```\n{SAMPLE_DIFF}\n```")
    _assert_valid_review(result.output)
