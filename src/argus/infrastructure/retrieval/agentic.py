"""Agentic retrieval strategy — LLM-guided context discovery via pydantic-ai."""

from __future__ import annotations

import logging

from dataclasses import dataclass, field

from pydantic import BaseModel
from pydantic_ai import Agent

from argus.domain.llm.value_objects import ModelConfig
from argus.domain.retrieval.strategies import RetrievalStrategy
from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.infrastructure.llm_providers.factory import create_agent
from argus.shared.constants import MAX_AGENTIC_ITERATIONS
from argus.shared.types import FilePath

logger = logging.getLogger(__name__)

# =============================================================================
# STRUCTURED OUTPUT SCHEMA
# =============================================================================

SYSTEM_PROMPT = """\
You are a code retrieval assistant. Given a diff and already-retrieved context,
generate search queries to find additional relevant code in the repository.

Respond with a list of keyword search queries and whether more context is needed.
Each query should target specific symbols, function names, or concepts that
appear in the diff but are not yet covered by the retrieved context.
"""


class SearchPlan(BaseModel):
    """Structured output from the agentic retrieval LLM."""

    queries: list[str]
    needs_more_context: bool


# =============================================================================
# STRATEGY
# =============================================================================


@dataclass
class AgenticRetrievalStrategy:
    """LLM-guided iterative retrieval.

    Uses a pydantic-ai Agent to generate search queries, delegates those
    queries to fallback strategies, and iterates until the LLM decides
    no more context is needed or max iterations are reached.
    """

    config: ModelConfig
    fallback_strategies: list[RetrievalStrategy]
    max_iterations: int = MAX_AGENTIC_ITERATIONS
    _agent: Agent[None, SearchPlan] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._agent = create_agent(
            config=self.config,
            output_type=SearchPlan,
            system_prompt=SYSTEM_PROMPT,
        )

    def retrieve(self, query: RetrievalQuery) -> list[ContextItem]:
        """Iteratively retrieve context using LLM-generated search queries."""
        all_items: dict[FilePath, ContextItem] = {}
        changed = set(query.changed_files)

        for iteration in range(self.max_iterations):
            user_prompt = self._build_prompt(query, list(all_items.values()))
            plan = self._agent.run_sync(user_prompt)

            if not plan.output.queries:
                logger.debug(
                    "Agentic retrieval: no queries at iteration %d",
                    iteration,
                )
                break

            new_items = self._execute_sub_queries(plan.output.queries, query, changed)

            for item in new_items:
                if item.source not in all_items:
                    all_items[item.source] = item

            if not plan.output.needs_more_context:
                break

        return list(all_items.values())

    def _build_prompt(
        self,
        query: RetrievalQuery,
        retrieved_so_far: list[ContextItem],
    ) -> str:
        """Build the user prompt for the LLM."""
        parts = [f"## Diff\n```\n{query.diff_text}\n```"]

        if query.changed_symbols:
            parts.append(f"## Changed symbols\n{', '.join(query.changed_symbols)}")

        if retrieved_so_far:
            sources = [item.source for item in retrieved_so_far]
            parts.append(f"## Already retrieved\n{', '.join(sources)}")

        parts.append("Generate search queries to find additional relevant context.")
        return "\n\n".join(parts)

    def _execute_sub_queries(
        self,
        queries: list[str],
        original_query: RetrievalQuery,
        changed: set[FilePath],
    ) -> list[ContextItem]:
        """Run sub-queries through fallback strategies."""
        items: list[ContextItem] = []

        for q in queries:
            sub_query = RetrievalQuery(
                changed_files=original_query.changed_files,
                changed_symbols=q.split(),
                diff_text=q,
            )
            for strategy in self.fallback_strategies:
                sub_items = strategy.retrieve(sub_query)
                for item in sub_items:
                    if item.source not in changed:
                        items.append(item)

        return items
