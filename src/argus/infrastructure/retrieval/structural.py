"""Structural retrieval strategy — graph-walk based."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.context.entities import CodebaseMap
from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.infrastructure.constants import CHARS_PER_TOKEN
from argus.shared.types import FilePath, TokenCount

# =============================================================================
# RELEVANCE SCORES
# =============================================================================

_DEPENDENT_SCORE = 0.9
_DEPENDENCY_SCORE = 0.8

# =============================================================================
# STRATEGY
# =============================================================================


@dataclass
class StructuralRetrievalStrategy:
    """Retrieves context by walking the dependency graph.

    For each changed file, collects direct dependents (what calls this)
    and direct dependencies (what this calls). Deterministic and instant.
    """

    codebase_map: CodebaseMap

    def retrieve(
        self, query: RetrievalQuery, budget: TokenCount | None = None
    ) -> list[ContextItem]:
        """Retrieve context items from the dependency graph."""
        related: dict[FilePath, float] = {}
        changed = set(query.changed_files)

        for changed_file in query.changed_files:
            for dep in self.codebase_map.graph.dependents_of(changed_file):
                if dep not in changed:
                    related[dep] = max(related.get(dep, 0.0), _DEPENDENT_SCORE)

            for dep in self.codebase_map.graph.dependencies_of(changed_file):
                if dep not in changed:
                    related[dep] = max(related.get(dep, 0.0), _DEPENDENCY_SCORE)

        # Sort by score descending so highest-relevance items are kept first.
        sorted_related = sorted(related.items(), key=lambda x: x[1], reverse=True)

        items: list[ContextItem] = []
        accumulated_tokens = 0
        for path, score in sorted_related:
            if path not in self.codebase_map:
                continue
            entry = self.codebase_map.get(path)
            content = self._build_content(entry.path, entry.exports)
            token_cost = TokenCount(max(1, len(content) // CHARS_PER_TOKEN))

            if budget is not None and accumulated_tokens + int(token_cost) > int(
                budget
            ):
                break

            items.append(
                ContextItem(
                    source=path,
                    content=content,
                    relevance_score=score,
                    token_cost=token_cost,
                )
            )
            accumulated_tokens += int(token_cost)

        return items

    def _build_content(self, path: FilePath, exports: list[str]) -> str:
        if exports:
            symbols = ", ".join(exports)
            return f"# {path}\nExports: {symbols}"
        return f"# {path}"
