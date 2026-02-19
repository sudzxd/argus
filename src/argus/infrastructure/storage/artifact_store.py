"""File-based CodebaseMap persistence."""

from __future__ import annotations

import hashlib
import logging

from dataclasses import dataclass
from pathlib import Path

from argus.domain.context.entities import CodebaseMap
from argus.domain.context.value_objects import ShardedManifest, ShardId
from argus.infrastructure.storage import serializer, shard_serializer

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"


def legacy_artifact_path(storage_dir: Path, repo_id: str) -> Path:
    """Compute the file path for a legacy flat artifact."""
    safe_name = hashlib.sha256(repo_id.encode()).hexdigest()[:16]
    return storage_dir / f"{safe_name}.json"


# =============================================================================
# ARTIFACT STORE
# =============================================================================


@dataclass
class FileArtifactStore:
    """Implements CodebaseMapRepository using local file storage."""

    storage_dir: Path

    def load(self, repo_id: str) -> CodebaseMap | None:
        """Load a CodebaseMap from disk.

        Returns:
            The stored map, or None if not found or corrupt.
        """
        path = self._path_for(repo_id)
        if not path.exists():
            return None

        try:
            data = path.read_text(encoding="utf-8")
            return serializer.deserialize(data)
        except (ValueError, KeyError):
            logger.warning("Corrupt artifact for %s, returning None", repo_id)
            return None

    def save(self, repo_id: str, codebase_map: CodebaseMap) -> None:
        """Persist a CodebaseMap to disk."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(repo_id)
        data = serializer.serialize(codebase_map)
        path.write_text(data, encoding="utf-8")

    def _path_for(self, repo_id: str) -> Path:
        return legacy_artifact_path(self.storage_dir, repo_id)


# =============================================================================
# SHARDED ARTIFACT STORE
# =============================================================================


@dataclass
class ShardedArtifactStore:
    """Sharded CodebaseMap persistence using per-directory shards.

    Stores a manifest.json plus one shard_<hash>.json per directory.
    Supports loading only specific shards for selective operations.

    Satisfies ``CodebaseMapRepository`` protocol via ``load`` / ``save``
    (which delegate to ``load_or_migrate`` / ``save_full``), so it can
    be wired into ``IndexingService`` and ``ReviewPullRequest``.
    """

    storage_dir: Path

    # ------------------------------------------------------------------
    # CodebaseMapRepository protocol
    # ------------------------------------------------------------------

    def load(self, repo_id: str) -> CodebaseMap | None:
        """Load the CodebaseMap, trying sharded then legacy format.

        Satisfies ``CodebaseMapRepository.load``.
        """
        return self.load_or_migrate(repo_id)

    def save(self, repo_id: str, codebase_map: CodebaseMap) -> None:
        """Persist a CodebaseMap in sharded format.

        Satisfies ``CodebaseMapRepository.save``.
        """
        self.save_full(repo_id, codebase_map)

    # ------------------------------------------------------------------
    # Sharded-specific API
    # ------------------------------------------------------------------

    def load_manifest(self, repo_id: str) -> ShardedManifest | None:
        """Load the shard manifest from disk.

        Returns:
            The manifest, or None if not found or corrupt.
        """
        path = self.storage_dir / MANIFEST_FILENAME
        if not path.exists():
            return None
        try:
            data = path.read_text(encoding="utf-8")
            return ShardedManifest.from_json(data)
        except (ValueError, KeyError):
            logger.warning("Corrupt manifest for %s, returning None", repo_id)
            return None

    def load_shards(
        self,
        repo_id: str,
        shard_ids: set[ShardId],
    ) -> CodebaseMap:
        """Load a partial CodebaseMap from specific shards."""
        manifest = self.load_manifest(repo_id)
        if manifest is None:
            from argus.shared.types import CommitSHA

            return CodebaseMap(indexed_at=CommitSHA(""))

        shard_data: dict[ShardId, str] = {}
        for sid in shard_ids:
            desc = manifest.shards.get(sid)
            if desc is None:
                continue
            blob_path = self.storage_dir / desc.blob_name
            if not blob_path.exists():
                logger.warning("Missing shard blob %s for %s", desc.blob_name, sid)
                continue
            shard_data[sid] = blob_path.read_text(encoding="utf-8")

        return shard_serializer.assemble_from_shards(manifest, shard_data)

    def save_shards(
        self,
        repo_id: str,
        manifest: ShardedManifest,
        changed_shard_ids: set[ShardId] | None = None,
    ) -> None:
        """Persist shards and manifest to disk.

        Args:
            repo_id: Repository identifier (unused, kept for protocol).
            manifest: The manifest to persist.
            changed_shard_ids: If provided, only shard data for these
                IDs should already exist in storage_dir. The manifest
                is always saved.
        """
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Save manifest.
        manifest_path = self.storage_dir / MANIFEST_FILENAME
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    def save_shard_data(self, shard_data: dict[ShardId, str]) -> None:
        """Write shard JSON files to disk."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # We need the manifest to get blob names — but the caller
        # already has the manifest. So we accept raw shard data
        # keyed by blob_name.
        for _sid, json_str in shard_data.items():
            # Compute blob name from content hash.
            content_hash = hashlib.sha256(json_str.encode()).hexdigest()[:16]
            blob_name = f"shard_{content_hash}.json"
            blob_path = self.storage_dir / blob_name
            blob_path.write_text(json_str, encoding="utf-8")

    def load_full(self, repo_id: str) -> CodebaseMap | None:
        """Load the complete CodebaseMap by loading all shards."""
        manifest = self.load_manifest(repo_id)
        if manifest is None:
            return None

        all_shard_ids = set(manifest.shards.keys())
        return self.load_shards(repo_id, all_shard_ids)

    def load_or_migrate(self, repo_id: str) -> CodebaseMap | None:
        """Load from sharded format, falling back to legacy flat format.

        If legacy format is found, it is returned as-is (migration
        to sharded format happens on next save).
        """
        # Try sharded format first.
        manifest = self.load_manifest(repo_id)
        if manifest is not None:
            return self.load_full(repo_id)

        # Fall back to legacy flat format.
        legacy_store = FileArtifactStore(storage_dir=self.storage_dir)
        return legacy_store.load(repo_id)

    def save_full(self, repo_id: str, codebase_map: CodebaseMap) -> None:
        """Split a full CodebaseMap into shards and save everything."""
        manifest, shard_data = shard_serializer.split_into_shards(codebase_map)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Write shard files.
        for sid, json_str in shard_data.items():
            desc = manifest.shards[sid]
            blob_path = self.storage_dir / desc.blob_name
            blob_path.write_text(json_str, encoding="utf-8")

        # Write manifest.
        manifest_path = self.storage_dir / MANIFEST_FILENAME
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")

        # Clean up legacy flat file if it exists.
        legacy_path = legacy_artifact_path(self.storage_dir, repo_id)
        if legacy_path.exists():
            legacy_path.unlink()
            logger.info("Removed legacy artifact %s", legacy_path.name)
