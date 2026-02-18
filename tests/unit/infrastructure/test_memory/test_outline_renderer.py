"""Tests for OutlineRenderer."""

from __future__ import annotations

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    Edge,
    EdgeKind,
    Symbol,
    SymbolKind,
)
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.shared.types import CommitSHA, FilePath, LineRange


def _make_entry(
    path: str,
    symbols: list[tuple[str, SymbolKind, str]],
) -> FileEntry:
    return FileEntry(
        path=FilePath(path),
        symbols=[
            Symbol(
                name=name,
                kind=kind,
                line_range=LineRange(1, 10),
                signature=sig,
            )
            for name, kind, sig in symbols
        ],
        imports=[],
        exports=[],
        last_indexed=CommitSHA("abc"),
    )


def _make_map(*entries: FileEntry) -> CodebaseMap:
    cbm = CodebaseMap(indexed_at=CommitSHA("abc"))
    for e in entries:
        cbm.upsert(e)
    return cbm


class TestOutlineRenderer:
    def test_render_includes_changed_files(self) -> None:
        entry = _make_entry(
            "main.py",
            [("main", SymbolKind.FUNCTION, "def main()")],
        )
        cbm = _make_map(entry)
        renderer = OutlineRenderer(token_budget=1000)

        text, outline = renderer.render(cbm, [FilePath("main.py")])

        assert "main.py" in text
        assert "def main()" in text
        assert outline.file_count == 1

    def test_render_includes_dependents(self) -> None:
        main = _make_entry("main.py", [("main", SymbolKind.FUNCTION, "")])
        utils = _make_entry("utils.py", [("helper", SymbolKind.FUNCTION, "")])
        cbm = _make_map(main, utils)
        cbm.graph.add_edge(
            Edge(
                source=FilePath("utils.py"),
                target=FilePath("main.py"),
                kind=EdgeKind.IMPORTS,
            )
        )
        renderer = OutlineRenderer(token_budget=1000)

        text, outline = renderer.render(cbm, [FilePath("main.py")])

        assert "utils.py" in text
        assert outline.file_count == 2

    def test_render_respects_budget(self) -> None:
        entries = [
            _make_entry(f"file{i}.py", [("func", SymbolKind.FUNCTION, "")])
            for i in range(100)
        ]
        cbm = _make_map(*entries)
        # Very small budget: only ~1 file worth of chars
        renderer = OutlineRenderer(token_budget=10)

        _text, outline = renderer.render(
            cbm,
            [FilePath(f"file{i}.py") for i in range(100)],
        )

        assert outline.file_count < 100

    def test_render_uses_signature_when_available(self) -> None:
        entry = _make_entry(
            "main.py",
            [("greet", SymbolKind.FUNCTION, "def greet(name: str) -> str")],
        )
        cbm = _make_map(entry)
        renderer = OutlineRenderer(token_budget=1000)

        text, _ = renderer.render(cbm, [FilePath("main.py")])

        assert "def greet(name: str) -> str" in text

    def test_render_uses_kind_name_when_no_signature(self) -> None:
        entry = _make_entry(
            "main.py",
            [("MyClass", SymbolKind.CLASS, "")],
        )
        cbm = _make_map(entry)
        renderer = OutlineRenderer(token_budget=1000)

        text, _ = renderer.render(cbm, [FilePath("main.py")])

        assert "class MyClass" in text

    def test_render_full_includes_all_files(self) -> None:
        entries = [
            _make_entry(f"file{i}.py", [("func", SymbolKind.FUNCTION, "")])
            for i in range(5)
        ]
        cbm = _make_map(*entries)
        renderer = OutlineRenderer(token_budget=10000)

        _text, outline = renderer.render_full(cbm)

        assert outline.file_count == 5
