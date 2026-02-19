"""Repository protocols for Codebase Memory."""

from __future__ import annotations

from typing import Protocol

from argus.domain.memory.value_objects import CodebaseMemory


class CodebaseMemoryRepository(Protocol):
    """Persistence port for codebase memory."""

    def load(self, repo_id: str) -> CodebaseMemory | None:
        """Load memory for a repository, or None if not found."""
        ...

    def save(self, memory: CodebaseMemory) -> None:
        """Persist memory for a repository."""
        ...
