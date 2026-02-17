"""Strategy protocols for the Retrieval bounded context."""

from __future__ import annotations

from typing import Protocol

from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery

# =============================================================================
# PROTOCOLS
# =============================================================================


class RetrievalStrategy(Protocol):
    """Interface for a retrieval strategy."""

    def retrieve(self, query: RetrievalQuery) -> list[ContextItem]:
        """Retrieve context items relevant to the query."""
        ...
