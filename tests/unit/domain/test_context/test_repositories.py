"""Tests for Context Engine repository protocols."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.repositories import CodebaseMapRepository, SourceParser
from argus.domain.context.value_objects import Symbol, SymbolKind
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# CodebaseMapRepository protocol conformance
# =============================================================================


def test_codebase_map_repository_protocol_accepts_conforming_class() -> None:
    @dataclass
    class FakeMapRepo:
        _store: dict[str, CodebaseMap]

        def load(self, repo_id: str) -> CodebaseMap | None:
            return self._store.get(repo_id)

        def save(self, repo_id: str, codebase_map: CodebaseMap) -> None:
            self._store[repo_id] = codebase_map

    repo: CodebaseMapRepository = FakeMapRepo(_store={})
    assert repo.load("org/repo") is None

    cbm = CodebaseMap(indexed_at=CommitSHA("abc123"))
    repo.save("org/repo", cbm)
    assert repo.load("org/repo") is cbm


def test_codebase_map_repository_save_and_load_roundtrip() -> None:
    @dataclass
    class InMemoryRepo:
        _store: dict[str, CodebaseMap]

        def load(self, repo_id: str) -> CodebaseMap | None:
            return self._store.get(repo_id)

        def save(self, repo_id: str, codebase_map: CodebaseMap) -> None:
            self._store[repo_id] = codebase_map

    repo: CodebaseMapRepository = InMemoryRepo(_store={})
    cbm = CodebaseMap(indexed_at=CommitSHA("abc123"))
    entry = FileEntry(
        path=FilePath("src/main.py"),
        symbols=[],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("abc123"),
    )
    cbm.upsert(entry)

    repo.save("org/repo", cbm)
    loaded = repo.load("org/repo")

    assert loaded is not None
    assert len(loaded) == 1
    assert loaded.get(FilePath("src/main.py")) is entry


# =============================================================================
# SourceParser protocol conformance
# =============================================================================


def test_source_parser_protocol_accepts_conforming_class() -> None:
    @dataclass
    class FakeParser:
        def parse(self, path: FilePath, content: str) -> FileEntry:
            return FileEntry(
                path=path,
                symbols=[
                    Symbol(
                        name="main",
                        kind=SymbolKind.FUNCTION,
                        line_range=LineRange(start=1, end=3),
                    )
                ],
                imports=[],
                exports=["main"],
                last_indexed=CommitSHA("000"),
            )

        def supported_languages(self) -> frozenset[str]:
            return frozenset({"python"})

    parser: SourceParser = FakeParser()
    entry = parser.parse(FilePath("main.py"), "def main(): pass")

    assert entry.path == FilePath("main.py")
    assert len(entry.symbols) == 1
    assert entry.symbols[0].name == "main"


def test_source_parser_supported_languages() -> None:
    @dataclass
    class MultiLangParser:
        def parse(self, path: FilePath, content: str) -> FileEntry:
            return FileEntry(
                path=path,
                symbols=[],
                imports=[],
                exports=[],
                last_indexed=CommitSHA("000"),
            )

        def supported_languages(self) -> frozenset[str]:
            return frozenset({"python", "typescript", "go"})

    parser: SourceParser = MultiLangParser()
    langs = parser.supported_languages()

    assert "python" in langs
    assert "typescript" in langs
    assert "go" in langs
    assert len(langs) == 3
