"""Value objects for the Codebase Memory bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from argus.shared.types import FilePath


class PatternCategory(StrEnum):
    """Categories of codebase patterns learned from analysis."""

    STYLE = "style"
    NAMING = "naming"
    ARCHITECTURE = "architecture"
    ERROR_HANDLING = "error_handling"
    TESTING = "testing"
    DEPENDENCY = "dependency"


@dataclass(frozen=True)
class PatternEntry:
    """A single learned codebase pattern."""

    category: PatternCategory
    description: str
    confidence: float
    examples: list[str] = field(default_factory=list[str])

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be in [0.0, 1.0], got {self.confidence}"
            raise ValueError(msg)


@dataclass(frozen=True)
class FileOutlineEntry:
    """A compact outline of a single file's public API."""

    path: FilePath
    symbols: list[str]


@dataclass(frozen=True)
class CodebaseOutline:
    """The full structural outline of a codebase."""

    entries: list[FileOutlineEntry]
    version: int = 0

    @property
    def file_count(self) -> int:
        return len(self.entries)


@dataclass(frozen=True)
class CodebaseMemory:
    """Persistent memory for a repository — outline + learned patterns."""

    repo_id: str
    outline: CodebaseOutline
    patterns: list[PatternEntry] = field(default_factory=list[PatternEntry])
    version: int = 0
