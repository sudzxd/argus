"""Domain-specific types that prevent primitive obsession."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# =============================================================================
# NEWTYPES
# =============================================================================


class FilePath(str):
    """A path to a source file within a repository."""


class CommitSHA(str):
    """A git commit SHA."""


class TokenCount(int):
    """A count of LLM tokens."""

    def __add__(self, other: object) -> TokenCount:
        if isinstance(other, int):
            return TokenCount(int.__add__(self, other))
        return NotImplemented

    def __sub__(self, other: object) -> TokenCount:
        if isinstance(other, int):
            return TokenCount(int.__sub__(self, other))
        return NotImplemented


# =============================================================================
# VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class LineRange:
    """An inclusive range of line numbers within a file."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start > self.end:
            msg = f"start ({self.start}) must not exceed end ({self.end})"
            raise ValueError(msg)

    def __len__(self) -> int:
        return self.end - self.start + 1

    def __contains__(self, line: object) -> bool:
        if isinstance(line, int):
            return self.start <= line <= self.end
        return NotImplemented


# =============================================================================
# ENUMS
# =============================================================================


class Severity(IntEnum):
    """Review comment severity, ordered by importance."""

    PRAISE = 0
    SUGGESTION = 1
    WARNING = 2
    CRITICAL = 3


class Category(IntEnum):
    """Review comment category."""

    STYLE = 0
    PERFORMANCE = 1
    BUG = 2
    SECURITY = 3
    ARCHITECTURE = 4
