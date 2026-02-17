"""Tests for structural retrieval strategy."""

from __future__ import annotations

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import Edge, EdgeKind
from argus.domain.retrieval.value_objects import RetrievalQuery
from argus.infrastructure.retrieval.structural import StructuralRetrievalStrategy
from argus.shared.types import CommitSHA, FilePath

# =============================================================================
# Helpers
# =============================================================================


def _make_entry(path: str) -> FileEntry:
    return FileEntry(
        path=FilePath(path),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("sha"),
    )


def _make_map_with_edges(
    files: list[str],
    edges: list[tuple[str, str]],
) -> CodebaseMap:
    cbm = CodebaseMap(indexed_at=CommitSHA("sha"))
    for f in files:
        cbm.upsert(_make_entry(f))
    for src, tgt in edges:
        cbm.graph.add_edge(
            Edge(
                source=FilePath(src),
                target=FilePath(tgt),
                kind=EdgeKind.IMPORTS,
            )
        )
    return cbm


# =============================================================================
# Tests
# =============================================================================


def test_returns_dependents_of_changed_file() -> None:
    cbm = _make_map_with_edges(
        files=["a.py", "b.py", "c.py"],
        edges=[("b.py", "a.py"), ("c.py", "a.py")],
    )
    strategy = StructuralRetrievalStrategy(codebase_map=cbm)
    query = RetrievalQuery(
        changed_files=[FilePath("a.py")],
        changed_symbols=[],
        diff_text="",
    )

    items = strategy.retrieve(query)
    sources = {item.source for item in items}

    assert FilePath("b.py") in sources
    assert FilePath("c.py") in sources


def test_returns_dependencies_of_changed_file() -> None:
    cbm = _make_map_with_edges(
        files=["a.py", "b.py"],
        edges=[("a.py", "b.py")],
    )
    strategy = StructuralRetrievalStrategy(codebase_map=cbm)
    query = RetrievalQuery(
        changed_files=[FilePath("a.py")],
        changed_symbols=[],
        diff_text="",
    )

    items = strategy.retrieve(query)
    sources = {item.source for item in items}

    assert FilePath("b.py") in sources


def test_excludes_changed_files_from_results() -> None:
    cbm = _make_map_with_edges(
        files=["a.py", "b.py"],
        edges=[("a.py", "b.py"), ("b.py", "a.py")],
    )
    strategy = StructuralRetrievalStrategy(codebase_map=cbm)
    query = RetrievalQuery(
        changed_files=[FilePath("a.py")],
        changed_symbols=[],
        diff_text="",
    )

    items = strategy.retrieve(query)
    sources = {item.source for item in items}

    assert FilePath("a.py") not in sources
    assert FilePath("b.py") in sources


def test_returns_empty_when_no_graph_edges() -> None:
    cbm = _make_map_with_edges(
        files=["a.py", "b.py"],
        edges=[],
    )
    strategy = StructuralRetrievalStrategy(codebase_map=cbm)
    query = RetrievalQuery(
        changed_files=[FilePath("a.py")],
        changed_symbols=[],
        diff_text="",
    )

    items = strategy.retrieve(query)

    assert items == []


def test_dependents_scored_higher_than_dependencies() -> None:
    cbm = _make_map_with_edges(
        files=["changed.py", "dependent.py", "dependency.py"],
        edges=[
            ("dependent.py", "changed.py"),
            ("changed.py", "dependency.py"),
        ],
    )
    strategy = StructuralRetrievalStrategy(codebase_map=cbm)
    query = RetrievalQuery(
        changed_files=[FilePath("changed.py")],
        changed_symbols=[],
        diff_text="",
    )

    items = strategy.retrieve(query)
    dep_item = next(i for i in items if i.source == FilePath("dependent.py"))
    dependency_item = next(i for i in items if i.source == FilePath("dependency.py"))

    assert dep_item.relevance_score > dependency_item.relevance_score


def test_content_includes_exports() -> None:
    cbm = CodebaseMap(indexed_at=CommitSHA("sha"))
    cbm.upsert(
        FileEntry(
            path=FilePath("utils.py"),
            symbols=[],
            imports=[],
            exports=["helper", "validate"],
            last_indexed=CommitSHA("sha"),
        )
    )
    cbm.upsert(_make_entry("main.py"))
    cbm.graph.add_edge(
        Edge(
            source=FilePath("main.py"),
            target=FilePath("utils.py"),
            kind=EdgeKind.IMPORTS,
        )
    )

    strategy = StructuralRetrievalStrategy(codebase_map=cbm)
    query = RetrievalQuery(
        changed_files=[FilePath("main.py")],
        changed_symbols=[],
        diff_text="",
    )

    items = strategy.retrieve(query)
    utils_item = next(i for i in items if i.source == FilePath("utils.py"))

    assert "helper" in utils_item.content
    assert "validate" in utils_item.content
