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
- confidence: how confident you are (0.0-1.0) that this is an intentional convention
- examples: 1-2 brief examples from the outline that demonstrate the pattern

Focus on patterns that a code reviewer should enforce when reviewing new PRs.
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
            result = agent.run_sync(f"## Codebase Outline\n```\n{outline_text}\n```")
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
