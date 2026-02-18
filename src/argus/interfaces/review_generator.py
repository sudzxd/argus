"""ReviewGeneratorPort implementation using pydantic-ai."""

from __future__ import annotations

import logging

from dataclasses import dataclass

from pydantic import BaseModel

from argus.domain.llm.value_objects import ModelConfig
from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewRequest, ReviewSummary
from argus.infrastructure.constants import CHARS_PER_TOKEN
from argus.infrastructure.llm_providers.factory import create_agent
from argus.shared.types import Category, FilePath, LineRange, Severity

logger = logging.getLogger(__name__)

# =============================================================================
# STRUCTURED OUTPUT SCHEMA
# =============================================================================

_SEVERITY_MAP: dict[str, Severity] = {
    "praise": Severity.PRAISE,
    "suggestion": Severity.SUGGESTION,
    "warning": Severity.WARNING,
    "critical": Severity.CRITICAL,
}

_CATEGORY_MAP: dict[str, Category] = {
    "style": Category.STYLE,
    "performance": Category.PERFORMANCE,
    "bug": Category.BUG,
    "security": Category.SECURITY,
    "architecture": Category.ARCHITECTURE,
}

# Overhead reserved for system prompt + generation output (in tokens).
_PROMPT_OVERHEAD_TOKENS = 2200

SYSTEM_PROMPT = """\
You are Argus, an expert code reviewer. Analyze the provided diff and codebase \
context, then produce a structured review.

Guidelines:
- Focus on bugs, security issues, and architectural problems first.
- Praise good patterns and clean code.
- Be specific: reference exact lines, explain *why* something is an issue.
- Provide concrete suggestions with replacement code when possible.
- Assign confidence (0.0-1.0) based on how certain you are about each finding.
- Use severity levels: praise, suggestion, warning, critical.
- Use categories: style, performance, bug, security, architecture.
- If a codebase outline is provided, use it to understand the broader architecture \
and catch breaking changes across module boundaries.
- If codebase patterns are provided, enforce them — flag deviations from established \
conventions and patterns.
"""


class ReviewOutput(BaseModel):
    """Structured output schema for pydantic-ai agent."""

    class CommentOutput(BaseModel):
        """A single review comment."""

        file: str
        line_start: int
        line_end: int
        severity: str
        category: str
        body: str
        confidence: float
        suggestion: str | None = None

    summary_description: str
    summary_risks: list[str]
    summary_strengths: list[str]
    summary_verdict: str
    comments: list[CommentOutput]


# =============================================================================
# GENERATOR
# =============================================================================


@dataclass
class LLMReviewGenerator:
    """Bridges ReviewGeneratorPort to pydantic-ai."""

    config: ModelConfig

    def generate(self, request: ReviewRequest) -> Review:
        """Generate a review from diff and context via LLM."""
        prompt = self._build_prompt(request)
        output = self._generate_tool_mode(prompt)
        return self._to_review(output)

    def _generate_tool_mode(self, prompt: str) -> ReviewOutput:
        """Use pydantic-ai tool calling for structured output."""
        agent = create_agent(
            config=self.config,
            output_type=ReviewOutput,
            system_prompt=SYSTEM_PROMPT,
        )
        result = agent.run_sync(prompt)
        return result.output

    def _build_prompt(self, request: ReviewRequest) -> str:
        """Assemble the user prompt with budget-aware section inclusion.

        Priority order (highest first): diff, retrieved context, outline, patterns.
        Lower-priority sections are dropped if they would exceed the token budget.
        """
        budget_chars = (
            int(self.config.max_tokens) - _PROMPT_OVERHEAD_TOKENS
        ) * CHARS_PER_TOKEN

        # Diff is always included (highest priority).
        diff_section = f"## Diff\n```\n{request.diff_text}\n```"
        used = len(diff_section)

        parts = [diff_section]

        # Retrieved context (second priority).
        if request.context.items:
            context_parts: list[str] = []
            for item in request.context.items:
                context_parts.append(f"### {item.source}\n```\n{item.content}\n```")
            context_section = "## Codebase Context\n" + "\n".join(context_parts)
            if used + len(context_section) <= budget_chars:
                parts.append(context_section)
                used += len(context_section)
            else:
                logger.info(
                    "Dropping retrieved context section (%d chars) — exceeds budget",
                    len(context_section),
                )

        # Codebase outline (third priority).
        if request.codebase_outline_text:
            outline_section = (
                "## Codebase Outline\n```\n" + request.codebase_outline_text + "\n```"
            )
            if used + len(outline_section) <= budget_chars:
                parts.append(outline_section)
                used += len(outline_section)
            else:
                logger.info(
                    "Dropping outline section (%d chars) — exceeds budget",
                    len(outline_section),
                )

        # Codebase patterns (fourth priority).
        if request.codebase_patterns_text:
            patterns_section = "## Codebase Patterns\n" + request.codebase_patterns_text
            if used + len(patterns_section) <= budget_chars:
                parts.append(patterns_section)
                used += len(patterns_section)
            else:
                logger.info(
                    "Dropping patterns section (%d chars) — exceeds budget",
                    len(patterns_section),
                )

        return "\n\n".join(parts)

    def _to_review(self, output: ReviewOutput) -> Review:
        """Convert pydantic output to domain Review entity."""
        summary = ReviewSummary(
            description=output.summary_description,
            risks=output.summary_risks,
            strengths=output.summary_strengths,
            verdict=output.summary_verdict,
        )
        comments = [self._to_comment(c) for c in output.comments]
        return Review(summary=summary, comments=comments)

    def _to_comment(self, c: ReviewOutput.CommentOutput) -> ReviewComment:
        return ReviewComment(
            file=FilePath(c.file),
            line_range=LineRange(c.line_start, c.line_end),
            severity=_SEVERITY_MAP.get(c.severity.lower(), Severity.SUGGESTION),
            category=_CATEGORY_MAP.get(c.category.lower(), Category.STYLE),
            body=c.body,
            confidence=c.confidence,
            suggestion=c.suggestion,
        )
