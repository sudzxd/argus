"""Tests that verify structured output schemas work through real Agent.run_sync().

Uses pydantic-ai's TestModel so no API keys are needed. These tests catch
schema issues that mock-based tests miss (e.g. nested model serialization,
field validation through the actual tool-calling path).
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from argus.domain.llm.value_objects import ModelConfig
from argus.infrastructure.llm_providers.factory import create_agent
from argus.infrastructure.retrieval.agentic import SearchPlan
from argus.interfaces.review_generator import ReviewOutput
from argus.shared.types import TokenCount


def _make_config() -> ModelConfig:
    return ModelConfig(
        model="test",
        max_tokens=TokenCount(4096),
        temperature=0.0,
    )


# =============================================================================
# ReviewOutput — the main review schema
# =============================================================================


def test_review_output_roundtrip_through_agent() -> None:
    """ReviewOutput schema works through real Agent.run_sync() with TestModel."""
    sample_args = {
        "summary_description": "SQL injection vulnerability introduced.",
        "summary_risks": ["SQL injection via f-string interpolation"],
        "summary_strengths": ["More readable string formatting"],
        "summary_verdict": "Changes introduce a critical security flaw.",
        "comments": [
            {
                "file": "utils.py",
                "line_start": 12,
                "line_end": 12,
                "severity": "critical",
                "category": "security",
                "body": "F-string interpolation in SQL is vulnerable to injection.",
                "confidence": 0.95,
                "suggestion": (
                    "cursor = conn.execute("
                    "'SELECT * FROM users WHERE id = ?', (user_id,))"
                ),
            }
        ],
    }

    model = TestModel(custom_output_args=sample_args)
    agent = create_agent(
        config=_make_config(),
        output_type=ReviewOutput,
        system_prompt="You are a code reviewer.",
    )

    result = agent.run_sync("Review this diff.", model=model)
    output = result.output

    assert output.summary_description == "SQL injection vulnerability introduced."
    assert len(output.comments) == 1
    assert output.comments[0].file == "utils.py"
    assert output.comments[0].severity == "critical"
    assert output.comments[0].suggestion is not None


def test_review_output_empty_comments() -> None:
    """ReviewOutput works with zero comments (clean diff)."""
    model = TestModel(
        custom_output_args={
            "summary_description": "Clean changes.",
            "summary_risks": [],
            "summary_strengths": ["Good test coverage"],
            "summary_verdict": "Approved.",
            "comments": [],
        }
    )
    agent = create_agent(
        config=_make_config(),
        output_type=ReviewOutput,
        system_prompt="You are a code reviewer.",
    )

    result = agent.run_sync("Review this diff.", model=model)

    assert result.output.comments == []
    assert result.output.summary_verdict == "Approved."


def test_review_output_multiple_comments() -> None:
    """ReviewOutput handles multiple comments with different severities."""
    model = TestModel(
        custom_output_args={
            "summary_description": "Mixed quality changes.",
            "summary_risks": ["Potential bug"],
            "summary_strengths": ["Good naming"],
            "summary_verdict": "Needs revision.",
            "comments": [
                {
                    "file": "a.py",
                    "line_start": 1,
                    "line_end": 3,
                    "severity": "critical",
                    "category": "bug",
                    "body": "Off-by-one error.",
                    "confidence": 0.9,
                    "suggestion": None,
                },
                {
                    "file": "b.py",
                    "line_start": 10,
                    "line_end": 10,
                    "severity": "praise",
                    "category": "style",
                    "body": "Great variable naming.",
                    "confidence": 0.8,
                    "suggestion": None,
                },
            ],
        }
    )
    agent = create_agent(
        config=_make_config(),
        output_type=ReviewOutput,
        system_prompt="You are a code reviewer.",
    )

    result = agent.run_sync("Review this diff.", model=model)

    assert len(result.output.comments) == 2
    assert result.output.comments[0].severity == "critical"
    assert result.output.comments[1].severity == "praise"


# =============================================================================
# SearchPlan — agentic retrieval schema
# =============================================================================


def test_search_plan_roundtrip_through_agent() -> None:
    """SearchPlan schema works through real Agent.run_sync() with TestModel."""
    model = TestModel(
        custom_output_args={
            "queries": ["helper function", "database connection"],
            "needs_more_context": True,
        }
    )
    agent = create_agent(
        config=_make_config(),
        output_type=SearchPlan,
        system_prompt="You are a retrieval assistant.",
    )

    result = agent.run_sync("Find context for this diff.", model=model)

    assert result.output.queries == ["helper function", "database connection"]
    assert result.output.needs_more_context is True


def test_search_plan_empty_queries() -> None:
    """SearchPlan works with no queries (LLM decides no more context needed)."""
    model = TestModel(
        custom_output_args={
            "queries": [],
            "needs_more_context": False,
        }
    )
    agent = create_agent(
        config=_make_config(),
        output_type=SearchPlan,
        system_prompt="You are a retrieval assistant.",
    )

    result = agent.run_sync("Find context for this diff.", model=model)

    assert result.output.queries == []
    assert result.output.needs_more_context is False
