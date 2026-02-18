"""Domain services for Codebase Memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from argus.domain.memory.value_objects import (
    CodebaseMemory,
    CodebaseOutline,
    PatternEntry,
)
from argus.shared.constants import MAX_PATTERN_ENTRIES, MIN_PATTERN_CONFIDENCE


class PatternAnalyzer(Protocol):
    """Port for analyzing codebase patterns via LLM."""

    def analyze(self, outline_text: str) -> list[PatternEntry]:
        """Analyze a codebase outline and return discovered patterns."""
        ...


@dataclass
class ProfileService:
    """Orchestrates building and updating codebase memory profiles.

    Handles pattern pruning (low confidence) and capping (max entries).
    """

    analyzer: PatternAnalyzer

    def build_profile(
        self,
        repo_id: str,
        outline: CodebaseOutline,
        outline_text: str,
    ) -> CodebaseMemory:
        """Build a fresh codebase memory profile.

        Args:
            repo_id: Repository identifier.
            outline: Structural outline of the codebase.
            outline_text: Rendered text of the outline for LLM analysis.

        Returns:
            A new CodebaseMemory with analyzed patterns.
        """
        raw_patterns = self.analyzer.analyze(outline_text)
        patterns = self._prune_and_cap(raw_patterns)
        return CodebaseMemory(
            repo_id=repo_id,
            outline=outline,
            patterns=patterns,
            version=1,
        )

    def update_profile(
        self,
        existing: CodebaseMemory,
        outline: CodebaseOutline,
        outline_text: str,
    ) -> CodebaseMemory:
        """Update an existing profile with fresh analysis.

        Merges new patterns with existing ones, re-prunes and re-caps.
        """
        new_patterns = self.analyzer.analyze(outline_text)

        # Merge: new patterns override existing ones with the same description.
        existing_map = {p.description: p for p in existing.patterns}
        for p in new_patterns:
            existing_map[p.description] = p

        merged = list(existing_map.values())
        patterns = self._prune_and_cap(merged)

        return CodebaseMemory(
            repo_id=existing.repo_id,
            outline=outline,
            patterns=patterns,
            version=existing.version + 1,
        )

    @staticmethod
    def _prune_and_cap(patterns: list[PatternEntry]) -> list[PatternEntry]:
        """Remove low-confidence patterns and cap at max entries."""
        pruned = [p for p in patterns if p.confidence >= MIN_PATTERN_CONFIDENCE]
        pruned.sort(key=lambda p: p.confidence, reverse=True)
        return pruned[:MAX_PATTERN_ENTRIES]
