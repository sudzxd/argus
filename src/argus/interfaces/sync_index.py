"""Incremental index command — updates codebase map for changed files only.

On push to main/develop, this entry point:
1. Pulls existing artifacts from the argus-data branch
2. Compares the stored ``indexed_at`` SHA against the push HEAD to find
   all files that changed since the last successful index — even if
   previous workflow runs were skipped
3. Incrementally updates the codebase map (no LLM calls)
4. Pushes updated artifacts back to argus-data

Falls back to a full bootstrap if no existing artifacts are found.

Usage:
    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
    GITHUB_EVENT_PATH=/path/to/push-event.json \
    uv run python -m argus.interfaces.sync_index
"""

from __future__ import annotations

import json
import logging
import os
import sys

from pathlib import Path

import httpx

from argus.domain.context.entities import CodebaseMap
from argus.domain.context.value_objects import ShardedManifest
from argus.infrastructure.constants import DATA_BRANCH
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.storage.artifact_store import ShardedArtifactStore
from argus.infrastructure.storage.git_branch_store import SelectiveGitBranchSync
from argus.interfaces.bootstrap import get_parseable_extensions
from argus.shared.exceptions import ArgusError, ConfigurationError, IndexingError
from argus.shared.types import CommitSHA, FilePath

logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(f"Missing required env var: {name}")
    return value


def _is_parseable(path: str, extensions: frozenset[str]) -> bool:
    """Check if a file path has a parseable extension."""
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    return ext in extensions


def _extract_after_sha(event_path: str) -> str:
    """Extract the HEAD (after) SHA from a push event payload."""
    with Path(event_path).open() as f:
        event: dict[str, object] = json.load(f)
    after = event.get("after")
    if not isinstance(after, str):
        msg = "Cannot extract 'after' SHA from push event"
        raise ConfigurationError(msg)
    return after


def run() -> None:
    """Incremental index: update codebase map for changed files only."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        _execute()
    except ArgusError as e:
        logger.error("Sync index failed: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error")
        sys.exit(1)


def _execute() -> None:
    token = _require_env("GITHUB_TOKEN")
    repo = _require_env("GITHUB_REPOSITORY")
    event_path = _require_env("GITHUB_EVENT_PATH")
    storage_dir = Path(os.environ.get("INPUT_STORAGE_DIR", ".argus-artifacts"))

    client = GitHubClient(token=token, repo=repo)
    parser = TreeSitterParser()
    sharded_store = ShardedArtifactStore(storage_dir=storage_dir)
    sync = SelectiveGitBranchSync(
        client=client,
        branch=DATA_BRANCH,
        storage_dir=storage_dir,
    )

    # 1. Pull manifest to check for existing artifacts.
    has_manifest = sync.pull_manifest()
    manifest = sharded_store.load_manifest(repo) if has_manifest else None

    after_sha = _extract_after_sha(event_path)

    if manifest is None:
        # Try legacy format via full pull.
        sync.pull_all()
        existing_map = sharded_store.load_or_migrate(repo)
        if existing_map is None:
            logger.info("No existing codebase map, falling back to full bootstrap")
            from argus.interfaces.bootstrap import run as bootstrap_run

            bootstrap_run()
            sync.push()
            return

        # Use stored indexed_at as the base SHA for comparison.
        base_sha = str(existing_map.indexed_at)
        _incremental_update_sharded(
            client,
            parser,
            sharded_store,
            existing_map,
            repo,
            base_sha,
            after_sha,
        )
    else:
        # Read indexed_at from the manifest — no shard pull needed.
        base_sha = str(manifest.indexed_at)
        logger.info(
            "Comparing from indexed_at=%s to HEAD=%s",
            base_sha[:8],
            after_sha[:8],
        )

        if base_sha == after_sha:
            logger.info("Already up to date at %s", after_sha[:8])
            return

        # Find changed files, then pull only the dirty shards.
        changed_paths = client.compare_commits(base_sha, after_sha)
        parseable = get_parseable_extensions()
        source_paths = [p for p in changed_paths if _is_parseable(p, parseable)]

        if not source_paths:
            logger.info("No parseable files changed, skipping update")
            return

        dirty_shard_ids = manifest.dirty_shards(
            [FilePath(p) for p in source_paths],
        )
        blob_names = {
            manifest.shards[sid].blob_name
            for sid in dirty_shard_ids
            if sid in manifest.shards
        }
        sync.pull_blobs(blob_names)

        # Load partial map from dirty shards only.
        partial_map = sharded_store.load_shards(repo, dirty_shard_ids)

        _incremental_update_sharded(
            client,
            parser,
            sharded_store,
            partial_map,
            repo,
            base_sha,
            after_sha,
            existing_manifest=manifest,
        )

    # 2. Push updated artifacts (merges with existing via base_tree).
    sync.push()


def _incremental_update_sharded(
    client: GitHubClient,
    parser: TreeSitterParser,
    store: ShardedArtifactStore,
    codebase_map: CodebaseMap,
    repo: str,
    before_sha: str,
    after_sha: str,
    existing_manifest: ShardedManifest | None = None,
) -> None:
    """Update the codebase map and re-shard only dirty directories."""
    changed_paths = client.compare_commits(before_sha, after_sha)
    parseable = get_parseable_extensions()
    source_paths = [p for p in changed_paths if _is_parseable(p, parseable)]

    if not source_paths:
        logger.info("No parseable files changed, skipping update")
        return

    logger.info(
        "Incrementally updating %d changed files (of %d total changed)",
        len(source_paths),
        len(changed_paths),
    )

    updated = 0
    for path_str in source_paths:
        fp = FilePath(path_str)
        try:
            content = client.get_file_content(fp, ref=after_sha)
            entry = parser.parse(fp, content)
            codebase_map.upsert(entry)
            updated += 1
        except (ArgusError, IndexingError, httpx.HTTPError) as e:
            logger.debug("Skipping %s: %s", path_str, e)

    codebase_map.indexed_at = CommitSHA(after_sha)
    logger.info("Updated %d files in codebase map", updated)

    if existing_manifest is not None:
        # Incremental save: merge new shard descriptors into existing manifest.
        store.save_incremental(existing_manifest, codebase_map)
    else:
        # Full save (legacy migration path).
        store.save_full(repo, codebase_map)


if __name__ == "__main__":
    run()
