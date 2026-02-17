"""ReviewGeneratorPort implementation using pydantic-ai."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from argus.domain.llm.value_objects import ModelConfig
from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewRequest, ReviewSummary
from argus.infrastructure.llm_providers.factory import create_agent
from argus.shared.types import Category, FilePath, LineRange, Severity

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
        """Generate a review from diff and context via LLM.

        Args:
            request: The review request with diff and context.

        Returns:
            A domain Review entity.
        """
        agent = create_agent(
            config=self.config,
            output_type=ReviewOutput,
            system_prompt=SYSTEM_PROMPT,
        )
        prompt = self._build_prompt(request)
        result = agent.run_sync(prompt)
        return self._to_review(result.output)

    def _build_prompt(self, request: ReviewRequest) -> str:
        """Assemble the user prompt from diff + context items."""
        parts = [f"## Diff\n```\n{request.diff_text}\n```"]

        if request.context.items:
            context_parts: list[str] = []
            for item in request.context.items:
                context_parts.append(f"### {item.source}\n```\n{item.content}\n```")
            parts.append("## Codebase Context\n" + "\n".join(context_parts))

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
