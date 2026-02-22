"""Tests for tree-sitter based source parser."""

from __future__ import annotations

import pytest

from argus.domain.context.entities import FileEntry
from argus.domain.context.value_objects import SymbolKind
from argus.infrastructure.constants import SupportedLanguage
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.shared.exceptions import IndexingError
from argus.shared.types import FilePath

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def parser() -> TreeSitterParser:
    return TreeSitterParser()


# =============================================================================
# Language detection
# =============================================================================


def test_supported_languages_returns_all_known(
    parser: TreeSitterParser,
) -> None:
    langs = parser.supported_languages()
    assert isinstance(langs, frozenset)
    for lang in SupportedLanguage:
        assert lang in langs


def test_language_for_path_detects_python(parser: TreeSitterParser) -> None:
    assert parser._language_for_path(FilePath("main.py")) == SupportedLanguage.PYTHON


def test_language_for_path_detects_javascript(parser: TreeSitterParser) -> None:
    js = SupportedLanguage.JAVASCRIPT
    assert parser._language_for_path(FilePath("app.js")) == js
    assert parser._language_for_path(FilePath("app.jsx")) == js


def test_language_for_path_detects_typescript(parser: TreeSitterParser) -> None:
    assert parser._language_for_path(FilePath("lib.ts")) == SupportedLanguage.TYPESCRIPT


def test_language_for_path_detects_go(parser: TreeSitterParser) -> None:
    assert parser._language_for_path(FilePath("main.go")) == SupportedLanguage.GO


def test_language_for_path_detects_rust(parser: TreeSitterParser) -> None:
    assert parser._language_for_path(FilePath("lib.rs")) == SupportedLanguage.RUST


def test_language_for_path_detects_java(parser: TreeSitterParser) -> None:
    assert parser._language_for_path(FilePath("App.java")) == SupportedLanguage.JAVA


def test_language_for_path_detects_cpp_variants(parser: TreeSitterParser) -> None:
    assert parser._language_for_path(FilePath("lib.cpp")) == SupportedLanguage.CPP
    assert parser._language_for_path(FilePath("lib.cc")) == SupportedLanguage.CPP
    assert parser._language_for_path(FilePath("lib.hpp")) == SupportedLanguage.CPP


def test_parser_raises_for_unsupported_extension(
    parser: TreeSitterParser,
) -> None:
    with pytest.raises(IndexingError, match="unsupported language"):
        parser.parse(FilePath("data.csv"), "a,b,c")


# =============================================================================
# Python parsing (real tree-sitter)
# =============================================================================


def test_parse_python_extracts_function(parser: TreeSitterParser) -> None:
    code = "def hello():\n    return 1\n"
    entry = parser.parse(FilePath("test.py"), code)

    assert isinstance(entry, FileEntry)
    assert entry.path == FilePath("test.py")
    assert len(entry.symbols) == 1
    assert entry.symbols[0].name == "hello"
    assert entry.symbols[0].kind == SymbolKind.FUNCTION


def test_parse_python_extracts_class_and_methods(
    parser: TreeSitterParser,
) -> None:
    code = (
        "class MyClass:\n"
        "    def method_a(self):\n"
        "        pass\n"
        "    def method_b(self):\n"
        "        pass\n"
    )
    entry = parser.parse(FilePath("models.py"), code)

    names = [s.name for s in entry.symbols]
    kinds = [s.kind for s in entry.symbols]

    assert "MyClass" in names
    assert "method_a" in names
    assert "method_b" in names
    assert kinds[names.index("MyClass")] == SymbolKind.CLASS
    assert kinds[names.index("method_a")] == SymbolKind.METHOD
    assert kinds[names.index("method_b")] == SymbolKind.METHOD


def test_parse_python_extracts_imports(parser: TreeSitterParser) -> None:
    code = "import os\nfrom pathlib import Path\n"
    entry = parser.parse(FilePath("app.py"), code)

    import_strs = [str(i) for i in entry.imports]
    assert "os" in import_strs
    assert "pathlib" in import_strs


def test_parse_python_extracts_exports(parser: TreeSitterParser) -> None:
    code = "def public_func():\n    pass\n\nclass PublicClass:\n    pass\n"
    entry = parser.parse(FilePath("lib.py"), code)

    assert "public_func" in entry.exports
    assert "PublicClass" in entry.exports


def test_parse_python_empty_file(parser: TreeSitterParser) -> None:
    entry = parser.parse(FilePath("empty.py"), "")

    assert entry.path == FilePath("empty.py")
    assert entry.symbols == []
    assert entry.imports == []
    assert entry.exports == []


def test_parse_python_line_ranges_are_1_indexed(
    parser: TreeSitterParser,
) -> None:
    code = "def first():\n    pass\n\ndef second():\n    pass\n"
    entry = parser.parse(FilePath("funcs.py"), code)

    first = next(s for s in entry.symbols if s.name == "first")
    second = next(s for s in entry.symbols if s.name == "second")

    assert first.line_range.start == 1
    assert second.line_range.start == 4


# =============================================================================
# Go parsing (real tree-sitter)
# =============================================================================


def test_parse_go_extracts_function(parser: TreeSitterParser) -> None:
    code = "package main\n\nfunc hello() int {\n\treturn 1\n}\n"
    entry = parser.parse(FilePath("main.go"), code)

    assert len(entry.symbols) >= 1
    func = next(s for s in entry.symbols if s.name == "hello")
    assert func.kind == SymbolKind.FUNCTION


# =============================================================================
# JavaScript parsing (real tree-sitter)
# =============================================================================


def test_parse_js_extracts_function(parser: TreeSitterParser) -> None:
    code = "function greet(name) {\n  return name;\n}\n"
    entry = parser.parse(FilePath("app.js"), code)

    assert len(entry.symbols) >= 1
    func = next(s for s in entry.symbols if s.name == "greet")
    assert func.kind == SymbolKind.FUNCTION


# =============================================================================
# Encoding robustness
# =============================================================================


def test_parse_handles_replacement_characters(parser: TreeSitterParser) -> None:
    """Non-UTF-8 replacement chars should not crash the parser."""
    code = "def hello():\n    x = '\ufffd'\n    return x\n"
    entry = parser.parse(FilePath("replaced.py"), code)

    assert entry.path == FilePath("replaced.py")
    assert len(entry.symbols) >= 1
