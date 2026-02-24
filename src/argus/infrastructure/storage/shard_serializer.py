"""Shard-level serialization for CodebaseMap.

Splits a CodebaseMap into per-directory shards and reassembles
partial maps from selected shards.
"""

from __future__ import annotations

import json
import logging

from argus.domain.context.entities import CodebaseMap, FileEntry
from argus.domain.context.value_objects import (
    CrossShardEdge,
    Edge,
    ShardDescriptor,
    ShardedManifest,
    ShardId,
    shard_id_for,
)
from argus.infrastructure.constants import SerializerField as F
from argus.infrastructure.storage._serial_helpers import (
    deserialize_edge,
    deserialize_entry,
    serialize_edge,
    serialize_entry,
)

logger = logging.getLogger(__name__)

# =============================================================================
# SHARD SERIALIZATION
# =============================================================================


def serialize_shard(
    entries: list[FileEntry],
    internal_edges: list[Edge],
) -> str:
    """Serialize a single shard's entries and internal edges to JSON."""
    data: dict[str, object] = {
        F.ENTRIES: [serialize_entry(e) for e in sorted(entries, key=lambda e: e.path)],
        F.EDGES: [serialize_edge(e) for e in internal_edges],
    }
    return json.dumps(data, indent=2)


def deserialize_shard(
    data: str,
) -> tuple[list[FileEntry], list[Edge]]:
    """Deserialize a shard JSON string into entries and edges.

    Raises:
        ValueError: If the JSON is malformed.
    """
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as e:
        msg = f"invalid shard JSON: {e}"
        raise ValueError(msg) from e

    entries: list[FileEntry] = []
    for entry_data in raw.get(F.ENTRIES, []):
        entries.append(deserialize_entry(entry_data))

    edges: list[Edge] = []
    for edge_data in raw.get(F.EDGES, []):
        edges.append(deserialize_edge(edge_data))

    return entries, edges


# =============================================================================
# SPLIT / ASSEMBLE
# =============================================================================


def split_into_shards(
    codebase_map: CodebaseMap,
) -> tuple[ShardedManifest, dict[ShardId, str]]:
    """Split a CodebaseMap into per-directory shards.

    Returns:
        A tuple of (manifest, shard_data) where shard_data maps
        ShardId to the serialized JSON string for that shard.
    """
    # Group entries by shard ID (parent directory).
    shard_entries: dict[ShardId, list[FileEntry]] = {}
    for path in sorted(codebase_map.files()):
        entry = codebase_map.get(path)
        sid = shard_id_for(path)
        shard_entries.setdefault(sid, []).append(entry)

    # Classify edges as internal or cross-shard.
    internal_edges: dict[ShardId, list[Edge]] = {}
    cross_shard_edges: list[CrossShardEdge] = []

    for edge in codebase_map.graph.edges:
        source_shard = shard_id_for(edge.source)
        target_shard = shard_id_for(edge.target)

        if source_shard == target_shard:
            internal_edges.setdefault(source_shard, []).append(edge)
        else:
            cross_shard_edges.append(
                CrossShardEdge(
                    source_shard=source_shard,
                    target_shard=target_shard,
                    source_file=edge.source,
                    target_file=edge.target,
                    kind=edge.kind,
                )
            )

    # Build shard data and descriptors.
    manifest = ShardedManifest(
        indexed_at=codebase_map.indexed_at,
        cross_shard_edges=cross_shard_edges,
    )
    shard_data: dict[ShardId, str] = {}

    for sid, entries in shard_entries.items():
        edges = internal_edges.get(sid, [])
        json_str = serialize_shard(entries, edges)
        content_hash = manifest.content_hash_for(json_str)
        blob_name = manifest.blob_name_for(content_hash)

        manifest.shards[sid] = ShardDescriptor(
            directory=sid,
            file_count=len(entries),
            content_hash=content_hash,
            blob_name=blob_name,
        )
        shard_data[sid] = json_str

    return manifest, shard_data


def assemble_from_shards(
    manifest: ShardedManifest,
    shard_data: dict[ShardId, str],
) -> CodebaseMap:
    """Assemble a (possibly partial) CodebaseMap from shard data.

    Args:
        manifest: The sharded manifest with cross-shard edges.
        shard_data: Map of ShardId to serialized shard JSON strings.

    Returns:
        A CodebaseMap containing entries and edges from the given shards.
    """
    codebase_map = CodebaseMap(indexed_at=manifest.indexed_at)

    loaded_shards: set[ShardId] = set()
    for sid, data in shard_data.items():
        entries, edges = deserialize_shard(data)
        for entry in entries:
            codebase_map.upsert(entry)
        for edge in edges:
            codebase_map.graph.add_edge(edge)
        loaded_shards.add(sid)

    # Restore cross-shard edges where both shards are loaded.
    restored = 0
    dropped = 0
    for cross_edge in manifest.cross_shard_edges:
        if (
            cross_edge.source_shard in loaded_shards
            and cross_edge.target_shard in loaded_shards
        ):
            codebase_map.graph.add_edge(
                Edge(
                    source=cross_edge.source_file,
                    target=cross_edge.target_file,
                    kind=cross_edge.kind,
                )
            )
            restored += 1
        else:
            dropped += 1

    if dropped > 0:
        logger.debug(
            "Restored %d cross-shard edges, dropped %d (shards not loaded)",
            restored,
            dropped,
        )

    return codebase_map
