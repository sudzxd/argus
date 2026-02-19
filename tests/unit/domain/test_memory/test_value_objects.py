"""Tests for memory domain value objects."""

from __future__ import annotations

import pytest

from argus.domain.memory.value_objects import (
    CodebaseMemory,
    CodebaseOutline,
    FileOutlineEntry,
    PatternCategory,
    PatternEntry,
)
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# PatternCategory
# =============================================================================


def test_pattern_category_has_all_members() -> None:
    members = {c.name for c in PatternCategory}
    assert members == {
        "STYLE",
        "NAMING",
        "ARCHITECTURE",
        "ERROR_HANDLING",
        "TESTING",
        "DEPENDENCY",
    }


# =============================================================================
# PatternEntry
# =============================================================================


def test_pattern_entry_stores_fields() -> None:
    entry = PatternEntry(
        category=PatternCategory.STYLE,
        description="Use snake_case for functions",
        confidence=0.9,
        examples=["def my_func(): ..."],
    )
    assert entry.category == PatternCategory.STYLE
    assert entry.description == "Use snake_case for functions"
    assert entry.confidence == 0.9
    assert entry.examples == ["def my_func(): ..."]


def test_pattern_entry_is_immutable() -> None:
    entry = PatternEntry(
        category=PatternCategory.STYLE,
        description="test",
        confidence=0.5,
    )
    with pytest.raises(AttributeError):
        entry.confidence = 0.8  # type: ignore[misc]


def test_pattern_entry_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence must be"):
        PatternEntry(
            category=PatternCategory.STYLE,
            description="bad",
            confidence=1.5,
        )


def test_pattern_entry_rejects_negative_confidence() -> None:
    with pytest.raises(ValueError, match="confidence must be"):
        PatternEntry(
            category=PatternCategory.STYLE,
            description="bad",
            confidence=-0.1,
        )


# =============================================================================
# FileOutlineEntry
# =============================================================================


def test_file_outline_entry_stores_fields() -> None:
    entry = FileOutlineEntry(
        path=FilePath("src/main.py"),
        symbols=["main", "helper"],
    )
    assert entry.path == FilePath("src/main.py")
    assert entry.symbols == ["main", "helper"]


# =============================================================================
# CodebaseOutline
# =============================================================================


def test_codebase_outline_file_count() -> None:
    outline = CodebaseOutline(
        entries=[
            FileOutlineEntry(path=FilePath("a.py"), symbols=["foo"]),
            FileOutlineEntry(path=FilePath("b.py"), symbols=["bar"]),
        ]
    )
    assert outline.file_count == 2


def test_codebase_outline_default_version() -> None:
    outline = CodebaseOutline(entries=[])
    assert outline.version == 0


# =============================================================================
# CodebaseMemory
# =============================================================================


def test_codebase_memory_stores_fields() -> None:
    outline = CodebaseOutline(entries=[])
    pattern = PatternEntry(
        category=PatternCategory.NAMING,
        description="PascalCase for classes",
        confidence=0.8,
    )
    memory = CodebaseMemory(
        repo_id="org/repo",
        outline=outline,
        patterns=[pattern],
        version=1,
    )
    assert memory.repo_id == "org/repo"
    assert memory.outline == outline
    assert len(memory.patterns) == 1
    assert memory.version == 1


def test_codebase_memory_default_version() -> None:
    memory = CodebaseMemory(
        repo_id="org/repo",
        outline=CodebaseOutline(entries=[]),
    )
    assert memory.version == 0
    assert memory.patterns == []


def test_codebase_memory_analyzed_at_default_none() -> None:
    memory = CodebaseMemory(
        repo_id="org/repo",
        outline=CodebaseOutline(entries=[]),
    )
    assert memory.analyzed_at is None


def test_codebase_memory_analyzed_at_stores_sha() -> None:
    sha = CommitSHA("abc123")
    memory = CodebaseMemory(
        repo_id="org/repo",
        outline=CodebaseOutline(entries=[]),
        analyzed_at=sha,
    )
    assert memory.analyzed_at == sha
