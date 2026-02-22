"""Value objects for the Context Engine bounded context."""

from __future__ import annotations

import hashlib
import json

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import NewType, cast

from argus.shared.types import CommitSHA, FilePath, LineRange

ShardId = NewType("ShardId", str)
"""Shard identifier — the POSIX parent directory of files in the shard."""

# =============================================================================
# ENUMS
# =============================================================================


class SymbolKind(StrEnum):
    """Kind of code symbol extracted from AST."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"


class EdgeKind(StrEnum):
    """Kind of relationship between files."""

    IMPORTS = "imports"
    CALLS = "calls"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"


# =============================================================================
# VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class Symbol:
    """A code symbol extracted from a source file."""

    name: str
    kind: SymbolKind
    line_range: LineRange
    signature: str = ""


@dataclass(frozen=True)
class Edge:
    """A directed relationship between two files."""

    source: FilePath
    target: FilePath
    kind: EdgeKind


@dataclass(frozen=True)
class Checkpoint:
    """An immutable snapshot reference for a CodebaseMap version."""

    commit_sha: CommitSHA
    version: str


# =============================================================================
# DEPENDENCY GRAPH
# =============================================================================


@dataclass
class DependencyGraph:
    """Directed graph of file-level relationships."""

    _edges: set[Edge] = field(default_factory=set[Edge])

    @property
    def edges(self) -> frozenset[Edge]:
        """All edges in the graph."""
        return frozenset(self._edges)

    def add_edge(self, edge: Edge) -> None:
        """Add a relationship to the graph."""
        self._edges.add(edge)

    def dependents_of(self, path: FilePath) -> set[FilePath]:
        """Files that depend on the given path (incoming edges)."""
        return {e.source for e in self._edges if e.target == path}

    def dependencies_of(self, path: FilePath) -> set[FilePath]:
        """Files that the given path depends on (outgoing edges)."""
        return {e.target for e in self._edges if e.source == path}

    def remove_file(self, path: FilePath) -> None:
        """Remove all edges involving the given file."""
        self._edges = {e for e in self._edges if e.source != path and e.target != path}

    def files(self) -> set[FilePath]:
        """All files referenced in the graph."""
        result: set[FilePath] = set()
        for e in self._edges:
            result.add(e.source)
            result.add(e.target)
        return result


# =============================================================================
# SHARDING VALUE OBJECTS
# =============================================================================


@dataclass(frozen=True)
class EmbeddingIndex:
    """Pre-computed embeddings for chunks in a shard."""

    shard_id: ShardId
    embeddings: list[list[float]]
    chunk_ids: list[str]  # "file:symbol_name"
    dimension: int
    model: str


def shard_id_for(path: FilePath) -> ShardId:
    """Derive the shard ID for a file from its parent directory."""
    return ShardId(str(PurePosixPath(path).parent))


@dataclass(frozen=True)
class ShardDescriptor:
    """Metadata for a single shard stored in the manifest."""

    directory: ShardId
    file_count: int
    content_hash: str
    blob_name: str


@dataclass(frozen=True)
class EmbeddingDescriptor:
    """Metadata for an embedding index stored in the manifest."""

    shard_id: ShardId
    model: str
    dimension: int
    blob_name: str


@dataclass(frozen=True)
class CrossShardEdge:
    """A dependency edge that crosses shard boundaries."""

    source_shard: ShardId
    target_shard: ShardId
    source_file: FilePath
    target_file: FilePath
    kind: EdgeKind


@dataclass
class ShardedManifest:
    """DAG index describing shards and cross-shard dependencies.

    The manifest is the root artifact stored on the argus-data branch.
    It maps shard IDs (directory paths) to their descriptors and tracks
    all dependency edges that cross shard boundaries.
    """

    indexed_at: CommitSHA
    shards: dict[ShardId, ShardDescriptor] = field(
        default_factory=dict[ShardId, ShardDescriptor],
    )
    cross_shard_edges: list[CrossShardEdge] = field(
        default_factory=list[CrossShardEdge],
    )
    embedding_indices: dict[ShardId, EmbeddingDescriptor] = field(
        default_factory=dict[ShardId, EmbeddingDescriptor],
    )

    def shards_for_files(self, paths: list[FilePath]) -> set[ShardId]:
        """Map file paths to their shard IDs."""
        return {shard_id_for(p) for p in paths}

    def adjacent_shards(
        self,
        shard_ids: set[ShardId],
        hops: int = 1,
    ) -> set[ShardId]:
        """BFS on cross-shard edge graph to find neighboring shards."""
        if not self.cross_shard_edges:
            return set()

        # Build adjacency from cross-shard edges.
        adj: dict[ShardId, set[ShardId]] = {}
        for edge in self.cross_shard_edges:
            adj.setdefault(edge.source_shard, set()).add(edge.target_shard)
            adj.setdefault(edge.target_shard, set()).add(edge.source_shard)

        visited: set[ShardId] = set()
        queue: deque[tuple[ShardId, int]] = deque()
        for sid in shard_ids:
            queue.append((sid, 0))

        while queue:
            current, depth = queue.popleft()
            if depth >= hops:
                continue
            for neighbor in adj.get(current, set()):
                if neighbor not in shard_ids and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return visited

    def dirty_shards(self, changed_files: list[FilePath]) -> set[ShardId]:
        """Return shard IDs affected by the given changed files."""
        return self.shards_for_files(changed_files)

    def content_hash_for(self, entries_json: str) -> str:
        """Compute a content hash for shard data."""
        return hashlib.sha256(entries_json.encode()).hexdigest()[:16]

    def blob_name_for(self, content_hash: str) -> str:
        """Generate a blob filename from a content hash."""
        return f"shard_{content_hash}.json"

    def to_dict(self) -> dict[str, object]:
        """Serialize manifest to a JSON-compatible dict."""
        shards: dict[str, dict[str, object]] = {}
        for sid, desc in self.shards.items():
            shards[sid] = {
                "directory": desc.directory,
                "file_count": desc.file_count,
                "content_hash": desc.content_hash,
                "blob_name": desc.blob_name,
            }

        edges: list[dict[str, str]] = []
        for edge in self.cross_shard_edges:
            edges.append(
                {
                    "source_shard": edge.source_shard,
                    "target_shard": edge.target_shard,
                    "source_file": edge.source_file,
                    "target_file": edge.target_file,
                    "kind": edge.kind.value,
                }
            )

        embeddings: dict[str, dict[str, object]] = {}
        for sid, desc in self.embedding_indices.items():
            embeddings[sid] = {
                "shard_id": desc.shard_id,
                "model": desc.model,
                "dimension": desc.dimension,
                "blob_name": desc.blob_name,
            }

        return {
            "version": 2,
            "indexed_at": str(self.indexed_at),
            "shards": shards,
            "cross_shard_edges": edges,
            "embedding_indices": embeddings,
        }

    def to_json(self) -> str:
        """Serialize manifest to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ShardedManifest:
        """Deserialize manifest from a dict."""
        indexed_at = CommitSHA(str(data["indexed_at"]))

        shards: dict[ShardId, ShardDescriptor] = {}
        raw_shards = data.get("shards", {})
        if isinstance(raw_shards, dict):
            shards_dict = cast(dict[str, object], raw_shards)
            for sid_str, desc_obj in shards_dict.items():
                if not isinstance(desc_obj, dict):
                    continue
                desc_data = cast(dict[str, object], desc_obj)
                sid = ShardId(sid_str)
                shards[sid] = ShardDescriptor(
                    directory=ShardId(str(desc_data["directory"])),
                    file_count=int(str(desc_data["file_count"])),
                    content_hash=str(desc_data["content_hash"]),
                    blob_name=str(desc_data["blob_name"]),
                )

        cross_shard_edges: list[CrossShardEdge] = []
        raw_edges = data.get("cross_shard_edges", [])
        if isinstance(raw_edges, list):
            edges_list = cast(list[object], raw_edges)
            for edge_obj in edges_list:
                if not isinstance(edge_obj, dict):
                    continue
                edge_data = cast(dict[str, object], edge_obj)
                cross_shard_edges.append(
                    CrossShardEdge(
                        source_shard=ShardId(str(edge_data["source_shard"])),
                        target_shard=ShardId(str(edge_data["target_shard"])),
                        source_file=FilePath(str(edge_data["source_file"])),
                        target_file=FilePath(str(edge_data["target_file"])),
                        kind=EdgeKind(str(edge_data["kind"])),
                    )
                )

        embedding_indices: dict[ShardId, EmbeddingDescriptor] = {}
        raw_embeddings = data.get("embedding_indices", {})
        if isinstance(raw_embeddings, dict):
            emb_dict = cast(dict[str, object], raw_embeddings)
            for sid_str, desc_obj in emb_dict.items():
                if not isinstance(desc_obj, dict):
                    continue
                desc_data = cast(dict[str, object], desc_obj)
                sid = ShardId(sid_str)
                embedding_indices[sid] = EmbeddingDescriptor(
                    shard_id=ShardId(str(desc_data["shard_id"])),
                    model=str(desc_data["model"]),
                    dimension=int(str(desc_data["dimension"])),
                    blob_name=str(desc_data["blob_name"]),
                )

        return cls(
            indexed_at=indexed_at,
            shards=shards,
            cross_shard_edges=cross_shard_edges,
            embedding_indices=embedding_indices,
        )

    @classmethod
    def from_json(cls, data: str) -> ShardedManifest:
        """Deserialize manifest from JSON string."""
        return cls.from_dict(json.loads(data))
