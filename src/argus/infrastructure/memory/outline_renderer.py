"""Renders codebase outlines from CodebaseMap for LLM consumption."""

from __future__ import annotations

import logging

from dataclasses import dataclass

from argus.domain.context.entities import CodebaseMap
from argus.domain.memory.value_objects import CodebaseOutline, FileOutlineEntry
from argus.infrastructure.constants import CHARS_PER_TOKEN
from argus.shared.types import FilePath

logger = logging.getLogger(__name__)


@dataclass
class OutlineRenderer:
    """Renders a compact codebase outline within a token budget.

    Scoping priority for changed-file rendering:
    1. Changed files themselves
    2. Direct dependents (files that import changed files)
    3. Direct dependencies (files imported by changed files)
    """

    token_budget: int

    def render(
        self,
        codebase_map: CodebaseMap,
        changed_files: list[FilePath],
    ) -> tuple[str, CodebaseOutline]:
        """Render an outline scoped to changed files and their blast radius.

        Returns:
            A tuple of (rendered text, structured outline).
        """
        # Collect files in priority order.
        ordered: list[FilePath] = []
        seen: set[FilePath] = set()

        # 1. Changed files.
        for f in changed_files:
            if f in codebase_map and f not in seen:
                ordered.append(f)
                seen.add(f)

        # 2. Dependents of changed files.
        for f in changed_files:
            for dep in sorted(codebase_map.graph.dependents_of(f)):
                if dep not in seen and dep in codebase_map:
                    ordered.append(dep)
                    seen.add(dep)

        # 3. Dependencies of changed files.
        for f in changed_files:
            for dep in sorted(codebase_map.graph.dependencies_of(f)):
                if dep not in seen and dep in codebase_map:
                    ordered.append(dep)
                    seen.add(dep)

        return self._render_files(codebase_map, ordered)

    def render_full(self, codebase_map: CodebaseMap) -> tuple[str, CodebaseOutline]:
        """Render an outline for the entire codebase map.

        Returns:
            A tuple of (rendered text, structured outline).
        """
        ordered = sorted(codebase_map.files())
        return self._render_files(codebase_map, ordered)

    def _render_files(
        self,
        codebase_map: CodebaseMap,
        files: list[FilePath],
    ) -> tuple[str, CodebaseOutline]:
        """Render file outlines within the token budget."""
        budget_chars = self.token_budget * CHARS_PER_TOKEN
        lines: list[str] = []
        outline_entries: list[FileOutlineEntry] = []
        used = 0

        for path in files:
            entry = codebase_map.get(path)
            file_lines: list[str] = [f"# {path}"]
            symbol_names: list[str] = []

            for sym in entry.symbols:
                if sym.signature:
                    file_lines.append(f"  {sym.signature}")
                else:
                    file_lines.append(f"  {sym.kind.value} {sym.name}")
                symbol_names.append(sym.name)

            section = "\n".join(file_lines) + "\n"
            if used + len(section) > budget_chars:
                logger.debug(
                    "Outline budget reached at %s (%d/%d chars)",
                    path,
                    used,
                    budget_chars,
                )
                break

            lines.append(section)
            used += len(section)
            outline_entries.append(FileOutlineEntry(path=path, symbols=symbol_names))

        outline = CodebaseOutline(entries=outline_entries)
        return "".join(lines), outline
