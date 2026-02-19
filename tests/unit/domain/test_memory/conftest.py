"""Fixtures for memory domain tests."""

from __future__ import annotations

import pytest

from argus.domain.memory.value_objects import (
    CodebaseOutline,
    FileOutlineEntry,
    PatternCategory,
    PatternEntry,
)
from argus.shared.types import FilePath


@pytest.fixture
def sample_outline() -> CodebaseOutline:
    return CodebaseOutline(
        entries=[
            FileOutlineEntry(path=FilePath("src/main.py"), symbols=["main"]),
            FileOutlineEntry(path=FilePath("src/utils.py"), symbols=["helper"]),
        ]
    )


@pytest.fixture
def sample_pattern() -> PatternEntry:
    return PatternEntry(
        category=PatternCategory.STYLE,
        description="Use snake_case for functions",
        confidence=0.9,
        examples=["def my_func(): ..."],
    )
