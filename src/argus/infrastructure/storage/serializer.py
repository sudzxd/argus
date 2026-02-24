"""CodebaseMap JSON serialization."""

from __future__ import annotations

import json

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import DependencyGraph
from argus.infrastructure.constants import SerializerField as F
from argus.infrastructure.storage._serial_helpers import (
    deserialize_edge,
    deserialize_entry,
    serialize_edge,
    serialize_entry,
)
from argus.shared.types import CommitSHA

# =============================================================================
# SERIALIZE
# =============================================================================


def serialize(codebase_map: CodebaseMap) -> str:
    """Serialize a CodebaseMap to a JSON string."""
    data = {
        F.INDEXED_AT: str(codebase_map.indexed_at),
        F.ENTRIES: [serialize_entry(e) for e in _iter_entries(codebase_map)],
        F.EDGES: [serialize_edge(e) for e in codebase_map.graph.edges],
    }
    return json.dumps(data, indent=2)


def _iter_entries(codebase_map: CodebaseMap) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for path in sorted(codebase_map.files()):
        entries.append(codebase_map.get(path))
    return entries


# =============================================================================
# DESERIALIZE
# =============================================================================


def deserialize(data: str) -> CodebaseMap:
    """Deserialize a JSON string into a CodebaseMap.

    Raises:
        ValueError: If the JSON is malformed or missing fields.
    """
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as e:
        msg = f"invalid JSON: {e}"
        raise ValueError(msg) from e

    codebase_map = CodebaseMap(indexed_at=CommitSHA(raw[F.INDEXED_AT]))

    for entry_data in raw.get(F.ENTRIES, []):
        entry = deserialize_entry(entry_data)
        codebase_map.upsert(entry)

    graph = DependencyGraph()
    for edge_data in raw.get(F.EDGES, []):
        graph.add_edge(deserialize_edge(edge_data))
    codebase_map.graph = graph

    return codebase_map
