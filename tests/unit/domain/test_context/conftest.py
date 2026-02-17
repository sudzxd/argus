"""Fixtures for Context Engine domain tests."""

from __future__ import annotations

import pytest

from argus.domain.context.value_objects import (
    DependencyGraph,
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.shared.types import CommitSHA, FilePath, LineRange


@pytest.fixture
def login_function() -> Symbol:
    return Symbol(
        name="login_user",
        kind=SymbolKind.FUNCTION,
        line_range=LineRange(start=10, end=25),
    )


@pytest.fixture
def auth_class() -> Symbol:
    return Symbol(
        name="AuthService",
        kind=SymbolKind.CLASS,
        line_range=LineRange(start=1, end=50),
    )


@pytest.fixture
def login_file(login_function: Symbol) -> tuple[FilePath, list[Symbol]]:
    return FilePath("src/auth/login.py"), [login_function]


@pytest.fixture
def models_file() -> tuple[FilePath, list[Symbol]]:
    return FilePath("src/db/models.py"), [
        Symbol(
            name="User",
            kind=SymbolKind.CLASS,
            line_range=LineRange(start=5, end=30),
        ),
    ]


@pytest.fixture
def import_edge() -> Edge:
    return Edge(
        source=FilePath("src/auth/login.py"),
        target=FilePath("src/db/models.py"),
        kind=EdgeKind.IMPORTS,
    )


@pytest.fixture
def empty_graph() -> DependencyGraph:
    return DependencyGraph()


@pytest.fixture
def sample_sha() -> CommitSHA:
    return CommitSHA("abc123def456")
