"""Tests for memory domain services."""

from __future__ import annotations

from argus.domain.memory.services import ProfileService
from argus.domain.memory.value_objects import (
    CodebaseOutline,
    FileOutlineEntry,
    PatternCategory,
    PatternEntry,
)
from argus.shared.types import FilePath


def _make_outline() -> CodebaseOutline:
    return CodebaseOutline(
        entries=[FileOutlineEntry(path=FilePath("main.py"), symbols=["main"])]
    )


def _make_patterns(n: int, confidence: float = 0.8) -> list[PatternEntry]:
    return [
        PatternEntry(
            category=PatternCategory.STYLE,
            description=f"Pattern {i}",
            confidence=confidence,
        )
        for i in range(n)
    ]


class FakeAnalyzer:
    """Fake PatternAnalyzer for testing."""

    def __init__(self, patterns: list[PatternEntry]) -> None:
        self._patterns = patterns

    def analyze(self, outline_text: str) -> list[PatternEntry]:
        return self._patterns

    def analyze_incremental(
        self,
        outline_text: str,
        existing_patterns: list[PatternEntry],
    ) -> list[PatternEntry]:
        return self._patterns


class TestProfileService:
    def test_build_profile_returns_memory(self) -> None:
        patterns = _make_patterns(3)
        service = ProfileService(analyzer=FakeAnalyzer(patterns))

        memory = service.build_profile("org/repo", _make_outline(), "outline text")

        assert memory.repo_id == "org/repo"
        assert memory.version == 1
        assert len(memory.patterns) == 3

    def test_build_profile_prunes_low_confidence(self) -> None:
        patterns = _make_patterns(3, confidence=0.1)
        service = ProfileService(analyzer=FakeAnalyzer(patterns))

        memory = service.build_profile("org/repo", _make_outline(), "text")

        assert len(memory.patterns) == 0

    def test_build_profile_caps_at_max_entries(self) -> None:
        patterns = _make_patterns(50, confidence=0.9)
        service = ProfileService(analyzer=FakeAnalyzer(patterns))

        memory = service.build_profile("org/repo", _make_outline(), "text")

        assert len(memory.patterns) == 30

    def test_update_profile_appends_new_patterns(self) -> None:
        from argus.domain.memory.value_objects import CodebaseMemory

        existing_patterns = [
            PatternEntry(
                category=PatternCategory.STYLE,
                description="Old pattern",
                confidence=0.8,
            ),
            PatternEntry(
                category=PatternCategory.NAMING,
                description="Naming pattern",
                confidence=0.7,
            ),
        ]
        existing = CodebaseMemory(
            repo_id="org/repo",
            outline=_make_outline(),
            patterns=existing_patterns,
            version=1,
        )

        # analyze_incremental returns only genuinely new patterns
        new_patterns = [
            PatternEntry(
                category=PatternCategory.ARCHITECTURE,
                description="New arch pattern",
                confidence=0.85,
            ),
        ]
        service = ProfileService(analyzer=FakeAnalyzer(new_patterns))

        memory = service.update_profile(existing, _make_outline(), "text")

        assert memory.version == 2
        # 2 existing + 1 new
        assert len(memory.patterns) == 3
        descs = {p.description for p in memory.patterns}
        assert "Old pattern" in descs
        assert "Naming pattern" in descs
        assert "New arch pattern" in descs

    def test_prune_and_cap_sorts_by_confidence(self) -> None:
        patterns = [
            PatternEntry(
                category=PatternCategory.STYLE,
                description="low",
                confidence=0.4,
            ),
            PatternEntry(
                category=PatternCategory.STYLE,
                description="high",
                confidence=0.95,
            ),
            PatternEntry(
                category=PatternCategory.STYLE,
                description="medium",
                confidence=0.7,
            ),
        ]
        result = ProfileService._prune_and_cap(patterns)

        assert [p.description for p in result] == ["high", "medium", "low"]
