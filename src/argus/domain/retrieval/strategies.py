"""Strategy protocols for the Retrieval bounded context."""

from __future__ import annotations

from typing import Protocol

from argus.domain.retrieval.value_objects import ContextItem, RetrievalQuery
from argus.shared.types import TokenCount

# =============================================================================
# PROTOCOLS
# =============================================================================


class RetrievalStrategy(Protocol):
    """Interface for a retrieval strategy."""

    def retrieve(
        self, query: RetrievalQuery, budget: TokenCount | None = None
    ) -> list[ContextItem]:
        """Retrieve context items relevant to the query."""
        ...
