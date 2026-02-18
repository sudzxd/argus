"""Infrastructure-layer constants and enums.

Eliminates magic strings across all infrastructure modules.
"""

from __future__ import annotations

from enum import StrEnum

# =============================================================================
# LANGUAGE IDENTIFIERS
# =============================================================================


class SupportedLanguage(StrEnum):
    """Language names recognized by the parser."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    RUBY = "ruby"
    KOTLIN = "kotlin"
    SWIFT = "swift"


class FileExtension(StrEnum):
    """File extensions mapped to languages."""

    PY = ".py"
    JS = ".js"
    JSX = ".jsx"
    TS = ".ts"
    TSX = ".tsx"
    GO = ".go"
    RS = ".rs"
    JAVA = ".java"
    C = ".c"
    H = ".h"
    CPP = ".cpp"
    CC = ".cc"
    CXX = ".cxx"
    HPP = ".hpp"
    RB = ".rb"
    KT = ".kt"
    KTS = ".kts"
    SWIFT = ".swift"


EXTENSION_TO_LANGUAGE: dict[FileExtension, SupportedLanguage] = {
    FileExtension.PY: SupportedLanguage.PYTHON,
    FileExtension.JS: SupportedLanguage.JAVASCRIPT,
    FileExtension.JSX: SupportedLanguage.JAVASCRIPT,
    FileExtension.TS: SupportedLanguage.TYPESCRIPT,
    FileExtension.TSX: SupportedLanguage.TYPESCRIPT,
    FileExtension.GO: SupportedLanguage.GO,
    FileExtension.RS: SupportedLanguage.RUST,
    FileExtension.JAVA: SupportedLanguage.JAVA,
    FileExtension.C: SupportedLanguage.C,
    FileExtension.H: SupportedLanguage.C,
    FileExtension.CPP: SupportedLanguage.CPP,
    FileExtension.CC: SupportedLanguage.CPP,
    FileExtension.CXX: SupportedLanguage.CPP,
    FileExtension.HPP: SupportedLanguage.CPP,
    FileExtension.RB: SupportedLanguage.RUBY,
    FileExtension.KT: SupportedLanguage.KOTLIN,
    FileExtension.KTS: SupportedLanguage.KOTLIN,
    FileExtension.SWIFT: SupportedLanguage.SWIFT,
}

LANGUAGE_TO_PACKAGE: dict[SupportedLanguage, str] = {
    SupportedLanguage.PYTHON: "tree_sitter_python",
    SupportedLanguage.JAVASCRIPT: "tree_sitter_javascript",
    SupportedLanguage.TYPESCRIPT: "tree_sitter_typescript",
    SupportedLanguage.GO: "tree_sitter_go",
    SupportedLanguage.RUST: "tree_sitter_rust",
    SupportedLanguage.JAVA: "tree_sitter_java",
    SupportedLanguage.C: "tree_sitter_c",
    SupportedLanguage.CPP: "tree_sitter_cpp",
    SupportedLanguage.RUBY: "tree_sitter_ruby",
    SupportedLanguage.KOTLIN: "tree_sitter_kotlin",
    SupportedLanguage.SWIFT: "tree_sitter_swift",
}


# =============================================================================
# TREE-SITTER NODE TYPES
# =============================================================================


class FunctionNodeType(StrEnum):
    """AST node types that represent function definitions."""

    FUNCTION_DEFINITION = "function_definition"
    FUNCTION_DECLARATION = "function_declaration"
    METHOD_DEFINITION = "method_definition"
    METHOD_DECLARATION = "method_declaration"


class ClassNodeType(StrEnum):
    """AST node types that represent class/struct definitions."""

    CLASS_DEFINITION = "class_definition"
    CLASS_DECLARATION = "class_declaration"
    STRUCT_DECLARATION = "struct_declaration"
    STRUCT_ITEM = "struct_item"
    ENUM_ITEM = "enum_item"
    TRAIT_ITEM = "trait_item"
    IMPL_ITEM = "impl_item"


class ImportNodeType(StrEnum):
    """AST node types that represent import statements."""

    IMPORT_STATEMENT = "import_statement"
    IMPORT_FROM_STATEMENT = "import_from_statement"
    USE_DECLARATION = "use_declaration"
    IMPORT_DECLARATION = "import_declaration"


class ImportPathNodeType(StrEnum):
    """AST child node types that carry an import path."""

    DOTTED_NAME = "dotted_name"
    MODULE_NAME = "module_name"
    STRING = "string"


FUNCTION_NODE_TYPES: frozenset[str] = frozenset(FunctionNodeType)
CLASS_NODE_TYPES: frozenset[str] = frozenset(ClassNodeType)
IMPORT_NODE_TYPES: frozenset[str] = frozenset(ImportNodeType)
DEFINITION_NODE_TYPES: frozenset[str] = FUNCTION_NODE_TYPES | CLASS_NODE_TYPES


# =============================================================================
# SERIALIZER FIELD NAMES
# =============================================================================


class SerializerField(StrEnum):
    """JSON field names for CodebaseMap serialization."""

    INDEXED_AT = "indexed_at"
    ENTRIES = "entries"
    EDGES = "edges"
    PATH = "path"
    SYMBOLS = "symbols"
    IMPORTS = "imports"
    EXPORTS = "exports"
    LAST_INDEXED = "last_indexed"
    SUMMARY = "summary"
    NAME = "name"
    KIND = "kind"
    LINE_START = "line_start"
    LINE_END = "line_end"
    SIGNATURE = "signature"
    SOURCE = "source"
    TARGET = "target"


# =============================================================================
# PROVIDER CONSTANTS
# =============================================================================


class GitHubAPI(StrEnum):
    """GitHub REST API constants."""

    BASE_URL = "https://api.github.com"
    ACCEPT_JSON = "application/vnd.github.v3+json"
    ACCEPT_DIFF = "application/vnd.github.v3.diff"
    PROVIDER_NAME = "github"


# =============================================================================
# REVIEW SEVERITY LABELS
# =============================================================================


class SeverityLabel(StrEnum):
    """Text prefixes for review comment severity levels."""

    CRITICAL = "[CRITICAL]"
    WARNING = "[WARNING]"
    SUGGESTION = "[SUGGESTION]"
    PRAISE = "[PRAISE]"


# =============================================================================
# TOKEN ESTIMATION
# =============================================================================

CHARS_PER_TOKEN = 4
"""Approximate characters per LLM token (conservative estimate)."""

MODULE_CHUNK_NAME = "<module>"
"""Default chunk name when a file has no symbols."""
