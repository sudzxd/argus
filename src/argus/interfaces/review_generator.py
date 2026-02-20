"""ReviewGeneratorPort implementation using pydantic-ai."""

from __future__ import annotations

import logging

from dataclasses import dataclass

from pydantic import BaseModel

from argus.domain.llm.value_objects import LLMUsage, ModelConfig
from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import PRContext, ReviewRequest, ReviewSummary
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
- When providing a suggestion, include ONLY the replacement code for the exact lines \
being commented on. No markdown fences, no extra context lines — the content will be \
wrapped in a GitHub suggestion block automatically.
- If a codebase outline is provided, use it to understand the broader architecture \
and catch breaking changes across module boundaries.
- If codebase patterns are provided, enforce them — flag deviations from established \
conventions and patterns.
- If PR context is provided, assess holistically: mention CI failures, flag stale PRs \
(>7 days open or behind base branch), note unaddressed reviewer feedback, and call out \
poor or missing PR descriptions.
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

    def generate(self, request: ReviewRequest) -> tuple[Review, LLMUsage]:
        """Generate a review from diff and context via LLM."""
        prompt = self._build_prompt(request)
        output, usage = self._generate_tool_mode(prompt)
        return self._to_review(output), usage

    def _generate_tool_mode(self, prompt: str) -> tuple[ReviewOutput, LLMUsage]:
        """Use pydantic-ai tool calling for structured output."""
        agent = create_agent(
            config=self.config,
            output_type=ReviewOutput,
            system_prompt=SYSTEM_PROMPT,
        )
        result = agent.run_sync(prompt)
        run_usage = result.usage()
        usage = LLMUsage(
            input_tokens=run_usage.input_tokens or 0,
            output_tokens=run_usage.output_tokens or 0,
            requests=run_usage.requests,
        )
        return result.output, usage

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

        # PR context (second priority).
        if request.pr_context is not None:
            pr_section = self._format_pr_context(request.pr_context)
            if used + len(pr_section) <= budget_chars:
                parts.append(pr_section)
                used += len(pr_section)
            else:
                logger.info(
                    "Dropping PR context section (%d chars) — exceeds budget",
                    len(pr_section),
                )

        # Retrieved context (third priority).
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

        # Codebase outline (fourth priority).
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

        # Codebase patterns (fifth priority).
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

    def _format_pr_context(self, ctx: PRContext) -> str:
        """Format PR context as a prompt section."""
        lines: list[str] = ["## PR Context"]
        lines.append(
            f"**Title:** {ctx.title} | **Author:** {ctx.author} "
            f"| **Open:** {ctx.git_health.days_open} days"
        )
        if ctx.labels:
            lines.append(f"**Labels:** {', '.join(ctx.labels)}")

        # CI status.
        ci = ctx.ci_status
        ci_label = (ci.conclusion or "pending").upper()
        lines.append(f"\n### CI Status: {ci_label}")
        for check in ci.checks:
            emoji = (
                "✅"
                if check.conclusion == "success"
                else "❌"
                if check.conclusion == "failure"
                else "⏳"
            )
            conclusion_str = check.conclusion or check.status
            entry = f"- {emoji} {check.name} ({conclusion_str})"
            if check.summary:
                entry += f': "{check.summary}"'
            lines.append(entry)

        # Git health.
        health = ctx.git_health
        warnings: list[str] = []
        if health.behind_by > 0:
            warnings.append(f"Behind base by {health.behind_by} commits")
        if health.has_merge_commits:
            warnings.append("Contains merge commits")
        if warnings:
            lines.append("\n### Git Health")
            for w in warnings:
                lines.append(f"- {w}")

        # Prior comments.
        if ctx.comments:
            lines.append(f"\n### Prior Comments ({len(ctx.comments)})")
            for c in ctx.comments:
                if c.file_path is not None:
                    loc = f"{c.file_path}:{c.line}" if c.line else c.file_path
                    lines.append(f'- @{c.author} on {loc} ({c.created_at}): "{c.body}"')
                else:
                    lines.append(f'- @{c.author} ({c.created_at}): "{c.body}"')

        # Related items.
        if ctx.related_items:
            lines.append("\n### Related Issues")
            for item in ctx.related_items:
                lines.append(f'- #{item.number} ({item.state}): "{item.title}"')

        # Description quality.
        if not ctx.body or len(ctx.body.strip()) < 10:
            lines.append("\n**Note:** PR description is missing or very short.")

        return "\n".join(lines)

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
