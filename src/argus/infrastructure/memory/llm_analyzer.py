"""LLM-based codebase pattern analyzer."""

from __future__ import annotations

import logging

from dataclasses import dataclass

from pydantic import BaseModel

from argus.domain.llm.value_objects import ModelConfig
from argus.domain.memory.value_objects import PatternCategory, PatternEntry
from argus.infrastructure.llm_providers.factory import create_agent
from argus.shared.exceptions import ProfileAnalysisError

logger = logging.getLogger(__name__)

_CATEGORY_MAP: dict[str, PatternCategory] = {
    "style": PatternCategory.STYLE,
    "naming": PatternCategory.NAMING,
    "architecture": PatternCategory.ARCHITECTURE,
    "error_handling": PatternCategory.ERROR_HANDLING,
    "testing": PatternCategory.TESTING,
    "dependency": PatternCategory.DEPENDENCY,
}

_SYSTEM_PROMPT = """\
You are a codebase analyst. Given a structural outline of a codebase, identify \
recurring patterns, conventions, and architectural decisions.

For each pattern, provide:
- category: one of style, naming, architecture, error_handling, testing, dependency
- description: a concise description of the pattern
- confidence: how confident you are (0.0-1.0) that this is a deliberate, \
project-specific convention (not just a language default or common practice)
- examples: 1-2 brief examples from the outline that demonstrate the pattern

Confidence calibration:
- 0.9-1.0: Pattern is unique to this project and clearly enforced everywhere
- 0.7-0.8: Strong signal across multiple files, likely intentional
- 0.5-0.6: Appears consistent but could be coincidence or standard practice
- 0.3-0.4: Weak signal, only a few examples, might not be intentional

Do NOT give high confidence to patterns that are just standard language idioms \
or framework defaults (e.g. using underscores for private methods in Python, \
having a tests/ directory). Focus on patterns that are specific to this project \
and that a reviewer should actively enforce.
"""

_INCREMENTAL_SYSTEM_PROMPT = """\
You are a codebase analyst. You are given:
1. A structural outline of the current codebase
2. A list of patterns already known about this codebase

Your job is to identify ONLY patterns that are NOT already covered by the \
existing list. Do NOT repeat, rephrase, or re-discover existing patterns. \
Two patterns "overlap" if they describe the same underlying convention, even \
if worded differently or at a different level of abstraction.

Only report a pattern if it is genuinely new — something not captured by any \
existing pattern entry. If nothing new stands out, return an empty list.

For each new pattern, provide:
- category: one of style, naming, architecture, error_handling, testing, dependency
- description: a concise description of the pattern
- confidence: how confident you are (0.0-1.0) that this is a deliberate, \
project-specific convention (not just a language default or common practice)
- examples: 1-2 brief examples from the outline that demonstrate the pattern

Confidence calibration:
- 0.9-1.0: Pattern is unique to this project and clearly enforced everywhere
- 0.7-0.8: Strong signal across multiple files, likely intentional
- 0.5-0.6: Appears consistent but could be coincidence or standard practice
- 0.3-0.4: Weak signal, only a few examples, might not be intentional

Do NOT give high confidence to patterns that are just standard language idioms \
or framework defaults. Focus on patterns specific to this project.
"""


class _PatternOutput(BaseModel):
    """Structured output for pattern analysis."""

    class Pattern(BaseModel):
        category: str
        description: str
        confidence: float
        examples: list[str] = []

    patterns: list[Pattern]


@dataclass
class LLMPatternAnalyzer:
    """Analyzes codebase outlines via LLM to discover patterns."""

    config: ModelConfig

    def analyze(self, outline_text: str) -> list[PatternEntry]:
        """Analyze a codebase outline and return discovered patterns.

        Raises:
            ProfileAnalysisError: If the LLM call fails.
        """
        try:
            agent = create_agent(
                config=self.config,
                output_type=_PatternOutput,
                system_prompt=_SYSTEM_PROMPT,
            )
            result = agent.run_sync(
                f"## Codebase Outline\n```\n{outline_text}\n```",
            )
            return [self._to_entry(p) for p in result.output.patterns]
        except Exception as e:
            raise ProfileAnalysisError(f"Pattern analysis failed: {e}") from e

    def analyze_incremental(
        self,
        outline_text: str,
        existing_patterns: list[PatternEntry],
    ) -> list[PatternEntry]:
        """Analyze a codebase outline, only returning genuinely new patterns.

        Raises:
            ProfileAnalysisError: If the LLM call fails.
        """
        if not existing_patterns:
            return self.analyze(outline_text)

        existing_text = _format_existing_patterns(existing_patterns)
        try:
            agent = create_agent(
                config=self.config,
                output_type=_PatternOutput,
                system_prompt=_INCREMENTAL_SYSTEM_PROMPT,
            )
            prompt = (
                f"## Existing Patterns\n{existing_text}\n\n"
                f"## Codebase Outline\n```\n{outline_text}\n```"
            )
            result = agent.run_sync(prompt)
            return [self._to_entry(p) for p in result.output.patterns]
        except Exception as e:
            raise ProfileAnalysisError(f"Pattern analysis failed: {e}") from e

    @staticmethod
    def _to_entry(p: _PatternOutput.Pattern) -> PatternEntry:
        category = _CATEGORY_MAP.get(p.category.lower())
        if category is None:
            logger.warning(
                "Unknown pattern category %r, defaulting to STYLE",
                p.category,
            )
            category = PatternCategory.STYLE
        confidence = max(0.0, min(1.0, p.confidence))
        return PatternEntry(
            category=category,
            description=p.description,
            confidence=confidence,
            examples=p.examples,
        )


def _format_existing_patterns(patterns: list[PatternEntry]) -> str:
    """Format existing patterns as text for the LLM prompt."""
    lines: list[str] = []
    for p in patterns:
        lines.append(f"- [{p.category.value}] {p.description}")
    return "\n".join(lines)
