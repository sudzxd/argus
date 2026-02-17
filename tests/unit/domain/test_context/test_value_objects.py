"""Tests for Context Engine value objects."""

from __future__ import annotations

import pytest

from argus.domain.context.value_objects import (
    Checkpoint,
    DependencyGraph,
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# Symbol
# =============================================================================


def test_symbol_stores_fields(login_function: Symbol) -> None:
    assert login_function.name == "login_user"
    assert login_function.kind == SymbolKind.FUNCTION
    assert login_function.line_range == LineRange(start=10, end=25)


def test_symbol_is_immutable(login_function: Symbol) -> None:
    with pytest.raises(AttributeError):
        login_function.name = "changed"  # type: ignore[misc]


def test_symbol_kind_has_all_members() -> None:
    members = {k.name for k in SymbolKind}
    assert members == {"FUNCTION", "CLASS", "METHOD", "VARIABLE", "IMPORT"}


# =============================================================================
# Edge
# =============================================================================


def test_edge_stores_fields(import_edge: Edge) -> None:
    assert import_edge.source == FilePath("src/auth/login.py")
    assert import_edge.target == FilePath("src/db/models.py")
    assert import_edge.kind == EdgeKind.IMPORTS


def test_edge_kind_has_all_members() -> None:
    members = {k.name for k in EdgeKind}
    assert members == {"IMPORTS", "CALLS", "EXTENDS", "IMPLEMENTS"}


def test_edge_is_immutable(import_edge: Edge) -> None:
    with pytest.raises(AttributeError):
        import_edge.kind = EdgeKind.CALLS  # type: ignore[misc]


# =============================================================================
# DependencyGraph
# =============================================================================


def test_graph_add_edge(empty_graph: DependencyGraph, import_edge: Edge) -> None:
    empty_graph.add_edge(import_edge)

    assert import_edge in empty_graph.edges


def test_graph_dependents_of(empty_graph: DependencyGraph, import_edge: Edge) -> None:
    empty_graph.add_edge(import_edge)
    target = FilePath("src/db/models.py")

    dependents = empty_graph.dependents_of(target)

    assert FilePath("src/auth/login.py") in dependents


def test_graph_dependencies_of(empty_graph: DependencyGraph, import_edge: Edge) -> None:
    empty_graph.add_edge(import_edge)
    source = FilePath("src/auth/login.py")

    deps = empty_graph.dependencies_of(source)

    assert FilePath("src/db/models.py") in deps


def test_graph_dependents_of_no_matches(
    empty_graph: DependencyGraph,
) -> None:
    result = empty_graph.dependents_of(FilePath("nonexistent.py"))
    assert result == set()


def test_graph_remove_file_removes_all_edges(
    empty_graph: DependencyGraph,
) -> None:
    login = FilePath("src/auth/login.py")
    models = FilePath("src/db/models.py")
    utils = FilePath("src/utils/jwt.py")

    empty_graph.add_edge(Edge(source=login, target=models, kind=EdgeKind.IMPORTS))
    empty_graph.add_edge(Edge(source=login, target=utils, kind=EdgeKind.IMPORTS))
    empty_graph.add_edge(Edge(source=utils, target=login, kind=EdgeKind.CALLS))

    empty_graph.remove_file(login)

    assert empty_graph.dependents_of(models) == set()
    assert empty_graph.dependencies_of(login) == set()
    assert empty_graph.dependents_of(login) == set()


def test_graph_files_returns_all_referenced_files(
    empty_graph: DependencyGraph, import_edge: Edge
) -> None:
    empty_graph.add_edge(import_edge)

    files = empty_graph.files()

    assert FilePath("src/auth/login.py") in files
    assert FilePath("src/db/models.py") in files


# =============================================================================
# Checkpoint
# =============================================================================


def test_checkpoint_stores_fields(sample_sha: CommitSHA) -> None:
    cp = Checkpoint(commit_sha=sample_sha, version="1.2.0")

    assert cp.commit_sha == sample_sha
    assert cp.version == "1.2.0"


def test_checkpoint_is_immutable(sample_sha: CommitSHA) -> None:
    cp = Checkpoint(commit_sha=sample_sha, version="1.0.0")

    with pytest.raises(AttributeError):
        cp.version = "2.0.0"  # type: ignore[misc]
