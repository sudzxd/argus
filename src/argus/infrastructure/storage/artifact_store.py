"""File-based CodebaseMap persistence."""

from __future__ import annotations

import hashlib
import logging

from dataclasses import dataclass
from pathlib import Path

from argus.domain.context.entities import CodebaseMap
from argus.infrastructure.storage import serializer

logger = logging.getLogger(__name__)

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
        safe_name = hashlib.sha256(repo_id.encode()).hexdigest()[:16]
        return self.storage_dir / f"{safe_name}.json"
