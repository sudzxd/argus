"""Git branch-based artifact storage using the Git Data API.

Stores and retrieves JSON artifacts on a dedicated orphan branch
(e.g. ``argus-data``), similar to how gh-pages deployment works.
"""

from __future__ import annotations

import base64
import logging

from dataclasses import dataclass, field
from pathlib import Path

from argus.infrastructure.github.client import GitHubClient

logger = logging.getLogger(__name__)


@dataclass
class GitBranchSync:
    """Sync JSON artifacts between a local directory and a Git branch.

    Args:
        client: GitHub API client.
        branch: Target branch name (e.g. ``argus-data``).
        storage_dir: Local directory for artifact files.
    """

    client: GitHubClient
    branch: str
    storage_dir: Path

    def pull(self) -> int:
        """Download artifacts from the branch to ``storage_dir``.

        Returns:
            Number of files downloaded.

        Raises:
            PublishError: If an API call fails (except missing branch).
        """
        ref_sha = self.client.get_ref_sha(self.branch)
        if ref_sha is None:
            logger.info("Branch %s does not exist, nothing to pull", self.branch)
            return 0

        tree_sha = self.client.get_commit_tree_sha(ref_sha)
        entries = self.client.get_tree_entries_flat(tree_sha)

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for entry in entries:
            entry_type = entry.get("type")
            entry_path = entry.get("path")
            entry_sha = entry.get("sha")

            if entry_type != "blob" or not isinstance(entry_path, str):
                continue
            if not entry_path.endswith(".json"):
                continue
            if not isinstance(entry_sha, str):
                continue

            content = self.client.get_blob_content(entry_sha)
            target = self.storage_dir / entry_path
            target.write_bytes(content)
            count += 1
            logger.debug("Downloaded %s", entry_path)

        logger.info("Pulled %d artifacts from %s", count, self.branch)
        return count

    def push(self) -> None:
        """Upload JSON artifacts from ``storage_dir`` to the branch.

        Creates an orphan commit if the branch doesn't exist yet,
        otherwise creates a new commit on top of the existing branch.

        Raises:
            PublishError: If an API call fails.
        """
        files = sorted(self.storage_dir.glob("*.json"))
        if not files:
            logger.info("No artifacts to push, skipping")
            return

        # Create blobs for each file.
        tree_entries: list[dict[str, str]] = []
        for file_path in files:
            content_b64 = base64.b64encode(file_path.read_bytes()).decode()
            blob_sha = self.client.create_blob(content_b64)
            tree_entries.append(
                {
                    "path": file_path.name,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )

        # Create tree (no base_tree — full replacement each time).
        tree_sha = self.client.create_tree(tree_entries)

        # Determine parent commits.
        ref_sha = self.client.get_ref_sha(self.branch)
        parents: list[str] = [ref_sha] if ref_sha else []

        # Create commit.
        commit_sha = self.client.create_commit(
            message=f"chore: update argus artifacts ({len(files)} files)",
            tree_sha=tree_sha,
            parents=parents,
        )

        # Create or update the branch ref.
        if ref_sha is None:
            self.client.create_ref(f"refs/heads/{self.branch}", commit_sha)
            logger.info("Created branch %s with %d artifacts", self.branch, len(files))
        else:
            self.client.update_ref(f"heads/{self.branch}", commit_sha)
            logger.info("Updated branch %s with %d artifacts", self.branch, len(files))


@dataclass
class SelectiveGitBranchSync:
    """Selective sync for sharded artifacts.

    Unlike ``GitBranchSync`` which downloads/uploads all blobs,
    this class can pull individual files (manifest, specific shards)
    and push using incremental tree updates via ``base_tree``.

    Tree entries are cached after the first pull so that subsequent
    ``pull_blobs`` calls avoid redundant API round-trips.
    """

    client: GitHubClient
    branch: str
    storage_dir: Path

    _cached_tree: list[dict[str, object]] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    """Cached tree entries from the last ``_fetch_tree`` call."""

    def _fetch_tree(self) -> list[dict[str, object]] | None:
        """Fetch and cache the branch tree entries.

        Returns:
            The tree entries, or None if the branch doesn't exist.
        """
        if self._cached_tree is not None:
            return self._cached_tree

        ref_sha = self.client.get_ref_sha(self.branch)
        if ref_sha is None:
            logger.info("Branch %s does not exist", self.branch)
            return None

        tree_sha = self.client.get_commit_tree_sha(ref_sha)
        self._cached_tree = self.client.get_tree_entries_flat(tree_sha)
        return self._cached_tree

    def pull_manifest(self) -> bool:
        """Download only manifest.json from the branch.

        Also caches tree entries for subsequent ``pull_blobs`` calls.

        Returns:
            True if manifest was downloaded, False if branch or file missing.
        """
        entries = self._fetch_tree()
        if entries is None:
            return False

        for entry in entries:
            entry_path = entry.get("path")
            entry_sha = entry.get("sha")
            if (
                entry_path == "manifest.json"
                and isinstance(entry_sha, str)
                and entry.get("type") == "blob"
            ):
                content = self.client.get_blob_content(entry_sha)
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                (self.storage_dir / "manifest.json").write_bytes(content)
                logger.debug("Downloaded manifest.json")
                return True

        logger.info("No manifest.json found on branch %s", self.branch)
        return False

    def pull_blobs(self, blob_names: set[str]) -> int:
        """Download specific blob files from the branch.

        Reuses tree entries cached by ``pull_manifest`` when available.

        Args:
            blob_names: Set of filenames to download (e.g. shard_abc.json).

        Returns:
            Number of files downloaded.
        """
        if not blob_names:
            return 0

        entries = self._fetch_tree()
        if entries is None:
            return 0

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for entry in entries:
            entry_path = entry.get("path")
            entry_sha = entry.get("sha")
            if (
                isinstance(entry_path, str)
                and entry_path in blob_names
                and isinstance(entry_sha, str)
                and entry.get("type") == "blob"
            ):
                content = self.client.get_blob_content(entry_sha)
                (self.storage_dir / entry_path).write_bytes(content)
                count += 1
                logger.debug("Downloaded %s", entry_path)

        logger.info("Pulled %d shard blobs from %s", count, self.branch)
        return count

    def memory_blob_names(self) -> set[str]:
        """Return filenames matching ``*_memory.json`` from cached tree.

        Must be called after ``pull_manifest`` (which populates the cache).
        Returns an empty set if no tree is cached.
        """
        if self._cached_tree is None:
            return set()
        names: set[str] = set()
        for entry in self._cached_tree:
            entry_path = entry.get("path")
            if (
                isinstance(entry_path, str)
                and entry_path.endswith("_memory.json")
                and entry.get("type") == "blob"
            ):
                names.add(entry_path)
        return names

    def pull_all(self) -> int:
        """Download all artifacts (manifest + all shards + memory).

        Returns:
            Number of files downloaded.
        """
        entries = self._fetch_tree()
        if entries is None:
            return 0

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for entry in entries:
            entry_type = entry.get("type")
            entry_path = entry.get("path")
            entry_sha = entry.get("sha")

            if entry_type != "blob" or not isinstance(entry_path, str):
                continue
            if not entry_path.endswith(".json"):
                continue
            if not isinstance(entry_sha, str):
                continue

            content = self.client.get_blob_content(entry_sha)
            target = self.storage_dir / entry_path
            target.write_bytes(content)
            count += 1
            logger.debug("Downloaded %s", entry_path)

        logger.info("Pulled %d artifacts from %s", count, self.branch)
        return count

    def push(self) -> None:
        """Upload all JSON artifacts from storage_dir to the branch.

        Uses full tree replacement (no base_tree) for simplicity.
        Clears the cached tree since branch state has changed.
        """
        files = sorted(self.storage_dir.glob("*.json"))
        if not files:
            logger.info("No artifacts to push, skipping")
            return

        tree_entries: list[dict[str, str]] = []
        for file_path in files:
            content_b64 = base64.b64encode(file_path.read_bytes()).decode()
            blob_sha = self.client.create_blob(content_b64)
            tree_entries.append(
                {
                    "path": file_path.name,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )

        tree_sha = self.client.create_tree(tree_entries)

        ref_sha = self.client.get_ref_sha(self.branch)
        parents: list[str] = [ref_sha] if ref_sha else []

        commit_sha = self.client.create_commit(
            message=f"chore: update argus artifacts ({len(files)} files)",
            tree_sha=tree_sha,
            parents=parents,
        )

        if ref_sha is None:
            self.client.create_ref(f"refs/heads/{self.branch}", commit_sha)
            logger.info("Created branch %s with %d artifacts", self.branch, len(files))
        else:
            self.client.update_ref(f"heads/{self.branch}", commit_sha)
            logger.info("Updated branch %s with %d artifacts", self.branch, len(files))

        # Invalidate cached tree — branch state has changed.
        self._cached_tree = None
