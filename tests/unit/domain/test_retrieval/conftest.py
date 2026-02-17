"""Fixtures for Retrieval domain tests."""

from __future__ import annotations

import pytest

from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.shared.types import FilePath, TokenCount


@pytest.fixture
def simple_query() -> RetrievalQuery:
    return RetrievalQuery(
        changed_files=[FilePath("src/auth/login.py")],
        changed_symbols=["login_user", "validate_token"],
        diff_text="- old_code\n+ new_code",
    )


@pytest.fixture
def context_item_high() -> ContextItem:
    return ContextItem(
        source=FilePath("src/auth/login.py"),
        content="def login_user(): ...",
        relevance_score=0.95,
        token_cost=TokenCount(100),
    )


@pytest.fixture
def context_item_low() -> ContextItem:
    return ContextItem(
        source=FilePath("src/utils/helpers.py"),
        content="def format_date(): ...",
        relevance_score=0.3,
        token_cost=TokenCount(50),
    )


@pytest.fixture
def context_item_medium() -> ContextItem:
    return ContextItem(
        source=FilePath("src/db/models.py"),
        content="class User: ...",
        relevance_score=0.7,
        token_cost=TokenCount(200),
    )
