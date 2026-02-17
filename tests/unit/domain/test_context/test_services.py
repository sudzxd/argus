"""Tests for Context Engine domain services."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.services import IndexingService
from argus.domain.context.value_objects import (
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.shared.exceptions import IndexingError
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# Fakes
# =============================================================================


@dataclass
class FakeParser:
    """Parser that returns a FileEntry with one symbol per file."""

    _fail_on: set[FilePath] = field(default_factory=set)

    def parse(self, path: FilePath, content: str) -> FileEntry:
        if path in self._fail_on:
            raise IndexingError(path, "unsupported language")
        return FileEntry(
            path=path,
            symbols=[
                Symbol(
                    name=f"sym_{path}",
                    kind=SymbolKind.FUNCTION,
                    line_range=LineRange(start=1, end=5),
                ),
            ],
            imports=[],
            exports=[f"sym_{path}"],
            last_indexed=CommitSHA("new_sha"),
        )

    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python"})


@dataclass
class FakeMapRepo:
    _store: dict[str, CodebaseMap] = field(default_factory=dict)

    def load(self, repo_id: str) -> CodebaseMap | None:
        return self._store.get(repo_id)

    def save(self, repo_id: str, codebase_map: CodebaseMap) -> None:
        self._store[repo_id] = codebase_map


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def parser() -> FakeParser:
    return FakeParser()


@pytest.fixture
def repo() -> FakeMapRepo:
    return FakeMapRepo()


@pytest.fixture
def service(parser: FakeParser, repo: FakeMapRepo) -> IndexingService:
    return IndexingService(parser=parser, repository=repo)


# =============================================================================
# Full indexing
# =============================================================================


def test_full_index_creates_new_map(service: IndexingService) -> None:
    file_contents = {
        FilePath("a.py"): "def a(): pass",
        FilePath("b.py"): "def b(): pass",
    }

    result = service.full_index(
        repo_id="org/repo",
        commit_sha=CommitSHA("sha1"),
        file_contents=file_contents,
    )

    assert result.files() == {FilePath("a.py"), FilePath("b.py")}
    assert result.indexed_at == CommitSHA("sha1")
    assert len(result) == 2


def test_full_index_saves_to_repository(
    service: IndexingService, repo: FakeMapRepo
) -> None:
    file_contents = {FilePath("a.py"): "def a(): pass"}

    service.full_index(
        repo_id="org/repo",
        commit_sha=CommitSHA("sha1"),
        file_contents=file_contents,
    )

    assert repo.load("org/repo") is not None
    assert len(repo.load("org/repo")) == 1  # type: ignore[arg-type]


def test_full_index_skips_unparseable_files(
    repo: FakeMapRepo,
) -> None:
    parser = FakeParser(_fail_on={FilePath("bad.py")})
    service = IndexingService(parser=parser, repository=repo)

    result = service.full_index(
        repo_id="org/repo",
        commit_sha=CommitSHA("sha1"),
        file_contents={
            FilePath("good.py"): "def g(): pass",
            FilePath("bad.py"): "???",
        },
    )

    assert FilePath("good.py") in result
    assert FilePath("bad.py") not in result


# =============================================================================
# Incremental indexing
# =============================================================================


def test_incremental_update_adds_new_files(
    service: IndexingService,
) -> None:
    existing = CodebaseMap(indexed_at=CommitSHA("old"))
    existing.upsert(
        FileEntry(
            path=FilePath("a.py"),
            symbols=[],
            imports=[],
            exports=[],
            last_indexed=CommitSHA("old"),
        )
    )

    result = service.incremental_update(
        codebase_map=existing,
        commit_sha=CommitSHA("new"),
        file_contents={FilePath("b.py"): "def b(): pass"},
    )

    assert FilePath("a.py") in result
    assert FilePath("b.py") in result
    assert result.indexed_at == CommitSHA("new")


def test_incremental_update_reparses_changed_files(
    service: IndexingService,
) -> None:
    existing = CodebaseMap(indexed_at=CommitSHA("old"))
    old_entry = FileEntry(
        path=FilePath("a.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("old"),
    )
    existing.upsert(old_entry)

    result = service.incremental_update(
        codebase_map=existing,
        commit_sha=CommitSHA("new"),
        file_contents={FilePath("a.py"): "def a_updated(): pass"},
    )

    updated_entry = result.get(FilePath("a.py"))
    assert updated_entry.last_indexed == CommitSHA("new_sha")
    assert updated_entry is not old_entry


def test_incremental_update_preserves_unchanged_files(
    service: IndexingService,
) -> None:
    existing = CodebaseMap(indexed_at=CommitSHA("old"))
    unchanged = FileEntry(
        path=FilePath("a.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("old"),
    )
    existing.upsert(unchanged)

    result = service.incremental_update(
        codebase_map=existing,
        commit_sha=CommitSHA("new"),
        file_contents={FilePath("b.py"): "def b(): pass"},
    )

    assert result.get(FilePath("a.py")) is unchanged


def test_incremental_update_removes_graph_edges_for_reparsed_files(
    service: IndexingService,
) -> None:
    existing = CodebaseMap(indexed_at=CommitSHA("old"))
    existing.upsert(
        FileEntry(
            path=FilePath("a.py"),
            symbols=[],
            imports=[FilePath("b.py")],
            exports=[],
            last_indexed=CommitSHA("old"),
        )
    )
    existing.graph.add_edge(
        Edge(
            source=FilePath("a.py"),
            target=FilePath("b.py"),
            kind=EdgeKind.IMPORTS,
        )
    )

    result = service.incremental_update(
        codebase_map=existing,
        commit_sha=CommitSHA("new"),
        file_contents={FilePath("a.py"): "# no more imports"},
    )

    # Old edge should be cleaned up since a.py was reparsed
    assert result.graph.dependencies_of(FilePath("a.py")) == set()


def test_incremental_update_skips_unparseable_keeps_old_entry(
    repo: FakeMapRepo,
) -> None:
    parser = FakeParser(_fail_on={FilePath("a.py")})
    service = IndexingService(parser=parser, repository=repo)

    existing = CodebaseMap(indexed_at=CommitSHA("old"))
    old_entry = FileEntry(
        path=FilePath("a.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("old"),
    )
    existing.upsert(old_entry)

    result = service.incremental_update(
        codebase_map=existing,
        commit_sha=CommitSHA("new"),
        file_contents={FilePath("a.py"): "???"},
    )

    # Old entry preserved when reparse fails
    assert result.get(FilePath("a.py")) is old_entry
