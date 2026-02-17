"""Tests for shared type definitions."""

from __future__ import annotations

import pytest

from argus.shared.types import (
    Category,
    CommitSHA,
    FilePath,
    LineRange,
    Severity,
    TokenCount,
)

# =============================================================================
# FilePath
# =============================================================================


def test_file_path_preserves_value(file_path: FilePath) -> None:
    assert str(file_path) == "src/auth/login.py"


def test_file_path_equality_same_value() -> None:
    assert FilePath("a.py") == FilePath("a.py")


def test_file_path_equality_different_value() -> None:
    assert FilePath("a.py") != FilePath("b.py")


def test_file_path_hashable_deduplicates() -> None:
    paths = {FilePath("a.py"), FilePath("b.py"), FilePath("a.py")}
    assert len(paths) == 2


# =============================================================================
# CommitSHA
# =============================================================================


def test_commit_sha_preserves_value(commit_sha: CommitSHA) -> None:
    assert str(commit_sha) == "a1b2c3d4e5f6"


def test_commit_sha_equality() -> None:
    assert CommitSHA("abc123") == CommitSHA("abc123")


# =============================================================================
# TokenCount
# =============================================================================


def test_token_count_preserves_value(token_count: TokenCount) -> None:
    assert int(token_count) == 1000


def test_token_count_addition() -> None:
    assert int(TokenCount(100) + TokenCount(200)) == 300


def test_token_count_subtraction() -> None:
    assert int(TokenCount(500) - TokenCount(200)) == 300


def test_token_count_less_than() -> None:
    assert TokenCount(100) < TokenCount(200)


def test_token_count_greater_than() -> None:
    assert TokenCount(200) > TokenCount(100)


def test_token_count_less_equal() -> None:
    assert TokenCount(100) <= TokenCount(100)


# =============================================================================
# LineRange
# =============================================================================


def test_line_range_stores_start_end(line_range: LineRange) -> None:
    assert line_range.start == 10
    assert line_range.end == 20


def test_line_range_length(line_range: LineRange) -> None:
    assert len(line_range) == 11


def test_line_range_contains_within(line_range: LineRange) -> None:
    assert 15 in line_range


def test_line_range_contains_outside(line_range: LineRange) -> None:
    assert 5 not in line_range


def test_line_range_single_line() -> None:
    lr = LineRange(start=5, end=5)
    assert len(lr) == 1


def test_line_range_invalid_raises() -> None:
    with pytest.raises(ValueError, match=r"start.*end"):
        LineRange(start=20, end=10)


# =============================================================================
# Severity
# =============================================================================


def test_severity_has_all_members() -> None:
    members = {s.name for s in Severity}
    assert members == {"CRITICAL", "WARNING", "SUGGESTION", "PRAISE"}


def test_severity_critical_outranks_warning() -> None:
    assert Severity.CRITICAL.value > Severity.WARNING.value


def test_severity_warning_outranks_suggestion() -> None:
    assert Severity.WARNING.value > Severity.SUGGESTION.value


def test_severity_suggestion_outranks_praise() -> None:
    assert Severity.SUGGESTION.value > Severity.PRAISE.value


# =============================================================================
# Category
# =============================================================================


def test_category_has_all_members() -> None:
    members = {c.name for c in Category}
    assert members == {"BUG", "SECURITY", "PERFORMANCE", "STYLE", "ARCHITECTURE"}
