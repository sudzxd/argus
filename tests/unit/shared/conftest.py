"""Fixtures for shared kernel tests."""

from __future__ import annotations

import pytest

from argus.shared.types import CommitSHA, FilePath, LineRange, TokenCount


@pytest.fixture
def file_path() -> FilePath:
    return FilePath("src/auth/login.py")


@pytest.fixture
def commit_sha() -> CommitSHA:
    return CommitSHA("a1b2c3d4e5f6")


@pytest.fixture
def token_count() -> TokenCount:
    return TokenCount(1000)


@pytest.fixture
def line_range() -> LineRange:
    return LineRange(start=10, end=20)
