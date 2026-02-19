"""Incremental index command — updates codebase map for changed files only.

On push to main/develop, this entry point:
1. Pulls existing artifacts from the argus-data branch
2. Determines which files changed in the push (via compare API)
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


def _extract_push_shas(event_path: str) -> tuple[str, str]:
    """Extract before/after SHAs from a push event payload.

    Returns:
        (before_sha, after_sha) tuple.
    """
    with Path(event_path).open() as f:
        event: dict[str, object] = json.load(f)
    before = event.get("before")
    after = event.get("after")
    if not isinstance(before, str) or not isinstance(after, str):
        msg = "Cannot extract before/after SHAs from push event"
        raise ConfigurationError(msg)
    return before, after


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

    if manifest is None:
        # Try legacy format via full pull.
        sync.pull_all()
        existing_map = sharded_store.load_or_migrate(repo)
        if existing_map is None:
            logger.info("No existing codebase map, falling back to full bootstrap")
            from argus.interfaces.bootstrap import run as bootstrap_run

            bootstrap_run()
            return

        # Incremental update on migrated legacy map.
        before_sha, after_sha = _extract_push_shas(event_path)
        _incremental_update_sharded(
            client,
            parser,
            sharded_store,
            existing_map,
            repo,
            before_sha,
            after_sha,
        )
    else:
        # Sharded path: pull only dirty shards.
        before_sha, after_sha = _extract_push_shas(event_path)
        changed_paths = client.compare_commits(before_sha, after_sha)
        parseable = get_parseable_extensions()
        source_paths = [p for p in changed_paths if _is_parseable(p, parseable)]

        if not source_paths:
            logger.info("No parseable files changed, skipping update")
            sync.push()
            return

        # Determine dirty shards and pull them.
        dirty_shard_ids = manifest.dirty_shards(
            [FilePath(p) for p in source_paths],
        )
        blob_names = {
            manifest.shards[sid].blob_name
            for sid in dirty_shard_ids
            if sid in manifest.shards
        }
        # Also pull memory file and any other blobs we need.
        sync.pull_blobs(blob_names)

        # Load partial map from dirty shards.
        partial_map = sharded_store.load_shards(repo, dirty_shard_ids)

        _incremental_update_sharded(
            client,
            parser,
            sharded_store,
            partial_map,
            repo,
            before_sha,
            after_sha,
        )

    # 2. Push updated artifacts.
    sync.push()


def _incremental_update_sharded(
    client: GitHubClient,
    parser: TreeSitterParser,
    store: ShardedArtifactStore,
    codebase_map: CodebaseMap,
    repo: str,
    before_sha: str,
    after_sha: str,
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

    # Re-shard and save. For incremental updates on a partial map,
    # we save the full partial map as shards — the push will merge
    # with existing blobs on the branch.
    store.save_full(repo, codebase_map)


if __name__ == "__main__":
    run()
