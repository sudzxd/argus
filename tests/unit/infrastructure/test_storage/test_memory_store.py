"""Tests for FileMemoryStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus.domain.memory.value_objects import (
    CodebaseMemory,
    CodebaseOutline,
    FileOutlineEntry,
    PatternCategory,
    PatternEntry,
)
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.shared.types import FilePath


@pytest.fixture
def storage_dir(tmp_path: Path) -> Path:
    return tmp_path / "memory"


@pytest.fixture
def store(storage_dir: Path) -> FileMemoryStore:
    return FileMemoryStore(storage_dir=storage_dir)


def _make_memory(repo_id: str = "org/repo") -> CodebaseMemory:
    outline = CodebaseOutline(
        entries=[
            FileOutlineEntry(path=FilePath("main.py"), symbols=["main", "helper"]),
        ],
        version=1,
    )
    patterns = [
        PatternEntry(
            category=PatternCategory.STYLE,
            description="Use snake_case",
            confidence=0.9,
            examples=["def my_func(): ..."],
        ),
    ]
    return CodebaseMemory(
        repo_id=repo_id,
        outline=outline,
        patterns=patterns,
        version=3,
    )


class TestFileMemoryStore:
    def test_load_returns_none_when_not_found(self, store: FileMemoryStore) -> None:
        result = store.load("nonexistent/repo")
        assert result is None

    def test_save_and_load_round_trip(self, store: FileMemoryStore) -> None:
        memory = _make_memory()
        store.save(memory)

        loaded = store.load("org/repo")

        assert loaded is not None
        assert loaded.repo_id == "org/repo"
        assert loaded.version == 3
        assert loaded.outline.version == 1
        assert len(loaded.outline.entries) == 1
        assert loaded.outline.entries[0].path == FilePath("main.py")
        assert loaded.outline.entries[0].symbols == ["main", "helper"]
        assert len(loaded.patterns) == 1
        assert loaded.patterns[0].category == PatternCategory.STYLE
        assert loaded.patterns[0].confidence == 0.9
        assert loaded.patterns[0].examples == ["def my_func(): ..."]

    def test_save_creates_storage_dir(
        self, storage_dir: Path, store: FileMemoryStore
    ) -> None:
        assert not storage_dir.exists()
        store.save(_make_memory())
        assert storage_dir.exists()

    def test_load_returns_none_for_corrupt_file(
        self, store: FileMemoryStore, storage_dir: Path
    ) -> None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        # Write a corrupt file.
        from argus.infrastructure.storage.memory_store import _repo_filename

        path = storage_dir / _repo_filename("org/repo")
        path.write_text("not json {{{")

        result = store.load("org/repo")
        assert result is None

    def test_different_repos_get_different_files(self, store: FileMemoryStore) -> None:
        mem1 = _make_memory("org/repo1")
        mem2 = _make_memory("org/repo2")
        store.save(mem1)
        store.save(mem2)

        loaded1 = store.load("org/repo1")
        loaded2 = store.load("org/repo2")

        assert loaded1 is not None
        assert loaded2 is not None
        assert loaded1.repo_id == "org/repo1"
        assert loaded2.repo_id == "org/repo2"
