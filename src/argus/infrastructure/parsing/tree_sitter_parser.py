"""Tree-sitter based source code parser."""

from __future__ import annotations

import importlib

from dataclasses import dataclass
from pathlib import PurePosixPath

from tree_sitter import Language, Node, Parser

from argus.domain.context.entities import FileEntry
from argus.domain.context.value_objects import Symbol, SymbolKind
from argus.infrastructure.constants import (
    CLASS_NODE_TYPES,
    DEFINITION_NODE_TYPES,
    EXTENSION_TO_LANGUAGE,
    FUNCTION_NODE_TYPES,
    IMPORT_NODE_TYPES,
    LANGUAGE_TO_PACKAGE,
    FileExtension,
    ImportPathNodeType,
    SupportedLanguage,
)
from argus.shared.exceptions import IndexingError
from argus.shared.types import CommitSHA, FilePath, LineRange

# =============================================================================
# LANGUAGE LOADING
# =============================================================================

_language_cache: dict[SupportedLanguage, Language] = {}


def _load_language(lang: SupportedLanguage) -> Language:
    """Load a tree-sitter Language from its package."""
    if lang in _language_cache:
        return _language_cache[lang]

    package_name = LANGUAGE_TO_PACKAGE.get(lang)
    if package_name is None:
        msg = f"no tree-sitter package for language: {lang}"
        raise ValueError(msg)

    module = importlib.import_module(package_name)

    if lang == SupportedLanguage.TYPESCRIPT and hasattr(module, "language_typescript"):
        ts_lang = Language(module.language_typescript())  # pyright: ignore[reportDeprecated]
    else:
        ts_lang = Language(module.language())  # pyright: ignore[reportDeprecated]

    _language_cache[lang] = ts_lang
    return ts_lang


# =============================================================================
# PARSER
# =============================================================================

_IDENTIFIER = "identifier"
_NAME_FIELD = "name"
_MAX_SIGNATURE_LEN = 120


@dataclass
class TreeSitterParser:
    """Parses source files into structured FileEntry using tree-sitter."""

    def parse(self, path: FilePath, content: str) -> FileEntry:
        """Parse a source file and extract symbols, imports, and exports.

        Args:
            path: File path within the repository.
            content: Raw source code.

        Returns:
            A FileEntry with extracted symbols and imports.

        Raises:
            IndexingError: If the language is unsupported or parsing fails.
        """
        lang = self._language_for_path(path)

        try:
            ts_lang = _load_language(lang)
        except (ValueError, ImportError) as e:
            raise IndexingError(path, f"failed to load grammar: {e}") from e

        try:
            parser = Parser(ts_lang)
            tree = parser.parse(content.encode("utf-8", errors="replace"))
        except Exception as e:
            raise IndexingError(path, f"parse failed: {e}") from e
        root = tree.root_node

        symbols = self._extract_symbols(root)
        imports = self._extract_imports(root)
        exports = self._extract_exports(root)

        return FileEntry(
            path=path,
            symbols=symbols,
            imports=imports,
            exports=exports,
            last_indexed=CommitSHA(""),
        )

    def supported_languages(self) -> frozenset[str]:
        """Return the set of supported language names."""
        return frozenset(SupportedLanguage)

    def _language_for_path(self, path: FilePath) -> SupportedLanguage:
        """Determine the language from a file's extension."""
        ext = PurePosixPath(str(path)).suffix.lower()
        try:
            file_ext = FileExtension(ext)
        except ValueError as e:
            raise IndexingError(path, "unsupported language") from e
        lang = EXTENSION_TO_LANGUAGE.get(file_ext)
        if lang is None:
            raise IndexingError(path, "unsupported language")
        return lang

    def _extract_symbols(self, root: Node) -> list[Symbol]:
        """Walk the AST and extract function/class symbols."""
        symbols: list[Symbol] = []
        self._walk_for_symbols(root, symbols, in_class=False)
        return symbols

    def _walk_for_symbols(
        self, node: Node, symbols: list[Symbol], *, in_class: bool
    ) -> None:
        for child in node.named_children:
            if child.type in FUNCTION_NODE_TYPES:
                name = self._get_node_name(child)
                if name:
                    kind = SymbolKind.METHOD if in_class else SymbolKind.FUNCTION
                    symbols.append(
                        Symbol(
                            name=name,
                            kind=kind,
                            line_range=LineRange(
                                start=child.start_point.row + 1,
                                end=child.end_point.row + 1,
                            ),
                            signature=self._extract_signature(child),
                        )
                    )
            elif child.type in CLASS_NODE_TYPES:
                name = self._get_node_name(child)
                if name:
                    symbols.append(
                        Symbol(
                            name=name,
                            kind=SymbolKind.CLASS,
                            line_range=LineRange(
                                start=child.start_point.row + 1,
                                end=child.end_point.row + 1,
                            ),
                            signature=self._extract_signature(child),
                        )
                    )
                self._walk_for_symbols(child, symbols, in_class=True)
                continue

            self._walk_for_symbols(child, symbols, in_class=in_class)

    @staticmethod
    def _extract_signature(node: Node) -> str:
        """Extract the first line of a node up to ':' or '{', truncated."""
        if node.text is None:
            return ""
        text = node.text.decode()
        # Take up to the first ':' or '{' delimiter
        for delim in (":", "{"):
            idx = text.find(delim)
            if idx >= 0:
                text = text[:idx]
                break
        # Take only the first line
        first_line = text.split("\n", 1)[0].strip()
        if len(first_line) > _MAX_SIGNATURE_LEN:
            return first_line[:_MAX_SIGNATURE_LEN]
        return first_line

    def _extract_imports(self, root: Node) -> list[FilePath]:
        imports: list[FilePath] = []
        for child in root.named_children:
            if child.type in IMPORT_NODE_TYPES:
                import_path = self._get_import_path(child)
                if import_path:
                    imports.append(FilePath(import_path))
        return imports

    def _extract_exports(self, root: Node) -> list[str]:
        exports: list[str] = []
        for child in root.named_children:
            if child.type in DEFINITION_NODE_TYPES:
                name = self._get_node_name(child)
                if name:
                    exports.append(name)
        return exports

    def _get_node_name(self, node: Node) -> str | None:
        name_node = node.child_by_field_name(_NAME_FIELD)
        if name_node is not None and name_node.text is not None:
            return name_node.text.decode()
        for child in node.named_children:
            if child.type == _IDENTIFIER and child.text is not None:
                return child.text.decode()
        return None

    def _get_import_path(self, node: Node) -> str | None:
        for child in node.named_children:
            if child.type in frozenset(ImportPathNodeType):
                if child.text is None:
                    continue
                text = child.text.decode()
                if child.type == ImportPathNodeType.STRING:
                    return text.strip("'\"")
                return text
        if node.named_children and node.named_children[0].text is not None:
            return node.named_children[0].text.decode()
        return None
