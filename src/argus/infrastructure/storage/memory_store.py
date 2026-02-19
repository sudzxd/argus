"""File-based persistence for CodebaseMemory."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from argus.domain.memory.value_objects import (
    CodebaseMemory,
    CodebaseOutline,
    FileOutlineEntry,
    PatternCategory,
    PatternEntry,
)
from argus.shared.types import CommitSHA, FilePath

logger = logging.getLogger(__name__)


def _repo_filename(repo_id: str) -> str:
    """Compute a stable filename from a repo ID."""
    digest = hashlib.sha256(repo_id.encode()).hexdigest()[:16]
    return f"{digest}_memory.json"


@dataclass
class FileMemoryStore:
    """Implements CodebaseMemoryRepository via JSON files with file locking."""

    storage_dir: Path

    def load(self, repo_id: str) -> CodebaseMemory | None:
        """Load memory for a repository, or None if not found."""
        path = self._path_for(repo_id)
        if not path.exists():
            return None

        try:
            with path.open("r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return _deserialize(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Corrupt memory file %s: %s", path, e)
            return None

    def save(self, memory: CodebaseMemory) -> None:
        """Persist memory for a repository."""
        path = self._path_for(memory.repo_id)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        data = _serialize(memory)
        with path.open("w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _path_for(self, repo_id: str) -> Path:
        return self.storage_dir / _repo_filename(repo_id)


# =============================================================================
# SERIALIZATION
# =============================================================================


def _serialize(memory: CodebaseMemory) -> dict[str, object]:
    data: dict[str, object] = {
        "repo_id": memory.repo_id,
        "version": memory.version,
        "outline": _serialize_outline(memory.outline),
        "patterns": [_serialize_pattern(p) for p in memory.patterns],
    }
    if memory.analyzed_at is not None:
        data["analyzed_at"] = str(memory.analyzed_at)
    return data


def _serialize_outline(outline: CodebaseOutline) -> dict[str, object]:
    return {
        "version": outline.version,
        "entries": [
            {"path": str(e.path), "symbols": e.symbols} for e in outline.entries
        ],
    }


def _serialize_pattern(pattern: PatternEntry) -> dict[str, object]:
    return {
        "category": pattern.category.value,
        "description": pattern.description,
        "confidence": pattern.confidence,
        "examples": pattern.examples,
    }


def _deserialize(data: dict[str, object]) -> CodebaseMemory:
    outline_raw = data["outline"]
    if not isinstance(outline_raw, dict):
        msg = "Invalid outline data"
        raise ValueError(msg)
    outline_data = cast(dict[str, object], outline_raw)

    entries: list[FileOutlineEntry] = []
    raw_entries = outline_data.get("entries", [])
    if isinstance(raw_entries, list):
        for e_raw in cast(list[object], raw_entries):
            if not isinstance(e_raw, dict):
                continue
            e = cast(dict[str, object], e_raw)
            raw_symbols = e.get("symbols", [])
            symbols: list[str] = []
            if isinstance(raw_symbols, list):
                symbols = [str(s) for s in cast(list[object], raw_symbols)]
            entries.append(
                FileOutlineEntry(
                    path=FilePath(str(e["path"])),
                    symbols=symbols,
                )
            )

    raw_version = outline_data.get("version", 0)
    outline = CodebaseOutline(
        entries=entries,
        version=int(raw_version) if isinstance(raw_version, (int, float)) else 0,
    )

    patterns: list[PatternEntry] = []
    raw_patterns = data.get("patterns", [])
    if isinstance(raw_patterns, list):
        for p_raw in cast(list[object], raw_patterns):
            if not isinstance(p_raw, dict):
                continue
            p = cast(dict[str, object], p_raw)
            raw_confidence = p["confidence"]
            raw_examples = p.get("examples", [])
            examples: list[str] = []
            if isinstance(raw_examples, list):
                examples = [str(x) for x in cast(list[object], raw_examples)]
            patterns.append(
                PatternEntry(
                    category=PatternCategory(str(p["category"])),
                    description=str(p["description"]),
                    confidence=_parse_confidence(raw_confidence),
                    examples=examples,
                )
            )

    raw_ver = data.get("version", 0)
    raw_analyzed_at = data.get("analyzed_at")
    analyzed_at = (
        CommitSHA(str(raw_analyzed_at)) if isinstance(raw_analyzed_at, str) else None
    )
    return CodebaseMemory(
        repo_id=str(data["repo_id"]),
        outline=outline,
        patterns=patterns,
        version=int(raw_ver) if isinstance(raw_ver, (int, float)) else 0,
        analyzed_at=analyzed_at,
    )


def _parse_confidence(raw: object) -> float:
    """Parse confidence value, warn and default to 0.5 on unexpected type."""
    if isinstance(raw, (int, float)):
        return float(raw)
    logger.warning("Unexpected confidence value %r, defaulting to 0.5", raw)
    return 0.5
