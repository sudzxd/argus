"""Live provider smoke tests — verify structured output works with real APIs.

These tests are SKIPPED by default. To run them:

    # Anthropic
    ANTHROPIC_API_KEY=sk-... uv run pytest tests/smoke -m anthropic

    # OpenAI
    OPENAI_API_KEY=sk-... uv run pytest tests/smoke -m openai

    # Local (LM Studio / vLLM / Ollama with OpenAI-compatible API)
    LOCAL_MODEL=qwen/qwen3-coder-30b LOCAL_BASE_URL=http://localhost:1234/v1 \
        uv run pytest tests/smoke -m local_llm

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
has_local = pytest.mark.skipif(
    not os.environ.get("LOCAL_MODEL") or not os.environ.get("LOCAL_BASE_URL"),
    reason="LOCAL_MODEL and LOCAL_BASE_URL not set",
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
    from argus.domain.retrieval.value_objects import RetrievalContext
    from argus.domain.review.value_objects import ReviewRequest

    config = ModelConfig(
        model="anthropic:claude-haiku-3-5-20241022",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )
    generator = LLMReviewGenerator(config=config)
    request = ReviewRequest(
        diff_text=SAMPLE_DIFF,
        context=RetrievalContext(items=[]),
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
# Local (OpenAI-compatible: LM Studio, vLLM, Ollama, etc.)
# =============================================================================


@has_local
@pytest.mark.local_llm
def test_local_model_structured_review() -> None:
    """Local OpenAI-compatible model returns valid structured ReviewOutput.

    Uses TextOutput mode (JSON in text response) since local models often
    have imperfect tool-calling support.
    """
    from pydantic_ai import Agent
    from pydantic_ai.output import TextOutput

    model_name = os.environ["LOCAL_MODEL"]
    base_url = os.environ["LOCAL_BASE_URL"]

    # Set base URL for the OpenAI client
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ.setdefault("OPENAI_API_KEY", "local")

    import json

    schema_json = json.dumps(ReviewOutput.model_json_schema(), indent=2)

    def parse_review(text: str) -> ReviewOutput:
        cleaned = text.strip()
        # Strip markdown fences
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            cleaned = cleaned[start:end]
        return ReviewOutput.model_validate_json(cleaned)

    agent = Agent(
        model=f"openai:{model_name}",
        output_type=TextOutput(parse_review),
        system_prompt=SYSTEM_PROMPT
        + f"\n\nRespond ONLY with a JSON object matching this schema:\n{schema_json}",
        model_settings={"max_tokens": 4096, "temperature": 0.0},
        retries=3,
    )

    result = agent.run_sync(f"## Diff\n```\n{SAMPLE_DIFF}\n```")
    _assert_valid_review(result.output)
