"""Tests for Context Engine entities."""

from __future__ import annotations

import pytest

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# FileEntry
# =============================================================================


@pytest.fixture
def file_entry() -> FileEntry:
    return FileEntry(
        path=FilePath("src/auth/login.py"),
        symbols=[
            Symbol(
                name="login_user",
                kind=SymbolKind.FUNCTION,
                line_range=LineRange(start=10, end=25),
            ),
        ],
        imports=[FilePath("src/db/models.py")],
        exports=["login_user"],
        last_indexed=CommitSHA("abc123"),
    )


def test_file_entry_stores_fields(file_entry: FileEntry) -> None:
    assert file_entry.path == FilePath("src/auth/login.py")
    assert len(file_entry.symbols) == 1
    assert file_entry.symbols[0].name == "login_user"
    assert file_entry.imports == [FilePath("src/db/models.py")]
    assert file_entry.exports == ["login_user"]
    assert file_entry.last_indexed == CommitSHA("abc123")


def test_file_entry_summary_defaults_none(file_entry: FileEntry) -> None:
    assert file_entry.summary is None


def test_file_entry_with_summary() -> None:
    entry = FileEntry(
        path=FilePath("src/main.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("abc"),
        summary="Application entry point.",
    )
    assert entry.summary == "Application entry point."


# =============================================================================
# CodebaseMap
# =============================================================================


@pytest.fixture
def codebase_map() -> CodebaseMap:
    return CodebaseMap(indexed_at=CommitSHA("abc123"))


@pytest.fixture
def populated_map(file_entry: FileEntry) -> CodebaseMap:
    cbm = CodebaseMap(indexed_at=CommitSHA("abc123"))
    cbm.upsert(file_entry)
    return cbm


def test_codebase_map_starts_empty(codebase_map: CodebaseMap) -> None:
    assert len(codebase_map) == 0
    assert codebase_map.indexed_at == CommitSHA("abc123")


def test_codebase_map_upsert_adds_entry(
    codebase_map: CodebaseMap, file_entry: FileEntry
) -> None:
    codebase_map.upsert(file_entry)

    assert len(codebase_map) == 1
    assert codebase_map.get(file_entry.path) is file_entry


def test_codebase_map_upsert_replaces_entry(
    populated_map: CodebaseMap,
) -> None:
    updated = FileEntry(
        path=FilePath("src/auth/login.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("def456"),
        summary="Updated.",
    )
    populated_map.upsert(updated)

    assert len(populated_map) == 1
    assert populated_map.get(FilePath("src/auth/login.py")).summary == "Updated."


def test_codebase_map_get_missing_raises(codebase_map: CodebaseMap) -> None:
    with pytest.raises(KeyError):
        codebase_map.get(FilePath("nonexistent.py"))


def test_codebase_map_remove_deletes_entry(
    populated_map: CodebaseMap,
) -> None:
    populated_map.remove(FilePath("src/auth/login.py"))

    assert len(populated_map) == 0


def test_codebase_map_remove_missing_raises(codebase_map: CodebaseMap) -> None:
    with pytest.raises(KeyError):
        codebase_map.remove(FilePath("nonexistent.py"))


def test_codebase_map_files_returns_all_paths(
    populated_map: CodebaseMap,
) -> None:
    paths = populated_map.files()

    assert FilePath("src/auth/login.py") in paths


def test_codebase_map_contains(populated_map: CodebaseMap) -> None:
    assert FilePath("src/auth/login.py") in populated_map
    assert FilePath("nonexistent.py") not in populated_map


def test_codebase_map_graph_tracks_edges(
    codebase_map: CodebaseMap,
) -> None:
    login = FilePath("src/auth/login.py")
    models = FilePath("src/db/models.py")

    entry = FileEntry(
        path=login,
        symbols=[],
        imports=[models],
        exports=[],
        last_indexed=CommitSHA("abc"),
    )
    codebase_map.upsert(entry)
    codebase_map.graph.add_edge(
        Edge(source=login, target=models, kind=EdgeKind.IMPORTS)
    )

    assert models in codebase_map.graph.dependencies_of(login)


def test_codebase_map_remove_cleans_graph(
    codebase_map: CodebaseMap,
) -> None:
    login = FilePath("src/auth/login.py")
    models = FilePath("src/db/models.py")

    entry = FileEntry(
        path=login,
        symbols=[],
        imports=[models],
        exports=[],
        last_indexed=CommitSHA("abc"),
    )
    codebase_map.upsert(entry)
    codebase_map.graph.add_edge(
        Edge(source=login, target=models, kind=EdgeKind.IMPORTS)
    )

    codebase_map.remove(login)

    assert codebase_map.graph.dependents_of(models) == set()
