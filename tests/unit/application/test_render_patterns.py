"""Tests for _render_patterns helper."""

from __future__ import annotations

from argus.application.review_pull_request import _render_patterns
from argus.domain.memory.value_objects import PatternCategory, PatternEntry


def test_render_patterns_formats_output() -> None:
    patterns = [
        PatternEntry(
            category=PatternCategory.STYLE,
            description="Use snake_case",
            confidence=0.9,
            examples=["def my_func(): ..."],
        ),
        PatternEntry(
            category=PatternCategory.ARCHITECTURE,
            description="Layer deps go downward",
            confidence=0.85,
            examples=["domain never imports infra", "app uses domain"],
        ),
    ]
    result = _render_patterns(patterns)

    assert "[style] Use snake_case" in result
    assert "(confidence: 0.9)" in result
    assert "Example: def my_func(): ..." in result
    assert "[architecture] Layer deps go downward" in result
    # Only first 2 examples
    assert "Example: domain never imports infra" in result
    assert "Example: app uses domain" in result
