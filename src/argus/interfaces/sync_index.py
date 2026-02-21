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
from argus.domain.llm.value_objects import ModelConfig
from argus.domain.memory.services import ProfileService
from argus.domain.memory.value_objects import CodebaseMemory
from argus.infrastructure.constants import DATA_BRANCH
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.storage.artifact_store import ShardedArtifactStore
from argus.infrastructure.storage.git_branch_store import SelectiveGitBranchSync
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.interfaces.bootstrap import get_parseable_extensions
from argus.interfaces.env_utils import (
    DEFAULT_INDEX_MAX_TOKENS,
    DEFAULT_INDEX_MODEL,
    require_env,
)
from argus.shared.constants import DEFAULT_OUTLINE_TOKEN_BUDGET
from argus.shared.exceptions import ArgusError, ConfigurationError, IndexingError
from argus.shared.types import CommitSHA, FilePath, TokenCount

logger = logging.getLogger(__name__)


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
    token = require_env("GITHUB_TOKEN")
    repo = require_env("GITHUB_REPOSITORY")
    event_path = require_env("GITHUB_EVENT_PATH")
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
        changed_files, codebase_map = _handle_legacy_path(
            client,
            parser,
            sharded_store,
            sync,
            repo,
            after_sha,
        )
        if changed_files is None:
            return
    else:
        changed_files, codebase_map = _handle_manifest_path(
            client,
            parser,
            sharded_store,
            sync,
            manifest,
            repo,
            after_sha,
        )
        if changed_files is None:
            return

    # 2. Optionally run incremental pattern analysis on changed files.
    if changed_files:
        _maybe_analyze_patterns(
            sync=sync,
            storage_dir=storage_dir,
            repo=repo,
            after_sha=after_sha,
            codebase_map=codebase_map,
            changed_files=changed_files,
        )

    # 2b. Optionally build embeddings for changed shards.
    _maybe_build_embeddings(
        storage_dir=storage_dir,
        codebase_map=codebase_map,
        changed_files=changed_files or [],
        client=client,
        after_sha=after_sha,
    )

    # 3. Push updated artifacts (merges with existing via base_tree).
    sync.push()


def _handle_legacy_path(
    client: GitHubClient,
    parser: TreeSitterParser,
    sharded_store: ShardedArtifactStore,
    sync: SelectiveGitBranchSync,
    repo: str,
    after_sha: str,
) -> tuple[list[FilePath] | None, CodebaseMap]:
    """Handle incremental update when no manifest exists (legacy format).

    Returns:
        Tuple of (changed_files, codebase_map). changed_files is None
        if the caller should return early (bootstrap fallback or no map).
    """
    sync.pull_all()
    existing_map = sharded_store.load_or_migrate(repo)
    if existing_map is None:
        logger.info("No existing codebase map, falling back to full bootstrap")
        from argus.interfaces.bootstrap import run as bootstrap_run

        bootstrap_run()
        sync.push()
        return None, CodebaseMap(indexed_at=CommitSHA(""))

    base_sha = str(existing_map.indexed_at)
    changed_files = _incremental_update_sharded(
        client,
        parser,
        sharded_store,
        existing_map,
        repo,
        base_sha,
        after_sha,
    )
    return changed_files, existing_map


def _handle_manifest_path(
    client: GitHubClient,
    parser: TreeSitterParser,
    sharded_store: ShardedArtifactStore,
    sync: SelectiveGitBranchSync,
    manifest: ShardedManifest,
    repo: str,
    after_sha: str,
) -> tuple[list[FilePath] | None, CodebaseMap]:
    """Handle incremental update using existing manifest.

    Returns:
        Tuple of (changed_files, codebase_map). changed_files is None
        if the caller should return early (already up to date or no changes).
    """
    base_sha = str(manifest.indexed_at)
    logger.info(
        "Comparing from indexed_at=%s to HEAD=%s",
        base_sha[:8],
        after_sha[:8],
    )

    if base_sha == after_sha:
        logger.info("Already up to date at %s", after_sha[:8])
        return None, CodebaseMap(indexed_at=CommitSHA(""))

    changed_paths = client.compare_commits(base_sha, after_sha)
    parseable = get_parseable_extensions()
    source_paths = [p for p in changed_paths if _is_parseable(p, parseable)]

    if not source_paths:
        logger.info("No parseable files changed, skipping update")
        return None, CodebaseMap(indexed_at=CommitSHA(""))

    dirty_shard_ids = manifest.dirty_shards(
        [FilePath(p) for p in source_paths],
    )
    blob_names = {
        manifest.shards[sid].blob_name
        for sid in dirty_shard_ids
        if sid in manifest.shards
    }
    sync.pull_blobs(blob_names)

    partial_map = sharded_store.load_shards(repo, dirty_shard_ids)

    changed_files = _incremental_update_sharded(
        client,
        parser,
        sharded_store,
        partial_map,
        repo,
        base_sha,
        after_sha,
        existing_manifest=manifest,
    )
    return changed_files, partial_map


def _maybe_analyze_patterns(
    sync: SelectiveGitBranchSync,
    storage_dir: Path,
    repo: str,
    after_sha: str,
    codebase_map: CodebaseMap,
    changed_files: list[FilePath],
) -> None:
    """Run incremental pattern analysis if opted in via INPUT_ANALYZE_PATTERNS."""
    if os.environ.get("INPUT_ANALYZE_PATTERNS", "false").lower() != "true":
        return

    model = os.environ.get("INPUT_MODEL", DEFAULT_INDEX_MODEL)
    max_tokens = int(os.environ.get("INPUT_MAX_TOKENS", str(DEFAULT_INDEX_MAX_TOKENS)))

    # Pull existing memory blobs.
    memory_blobs = sync.memory_blob_names()
    if memory_blobs:
        sync.pull_blobs(memory_blobs)

    memory_store = FileMemoryStore(storage_dir=storage_dir)
    existing_memory = memory_store.load(repo)

    if existing_memory is None:
        logger.info("No existing memory, skipping pattern analysis (use bootstrap)")
        return

    logger.info(
        "Running incremental pattern analysis on %d changed files",
        len(changed_files),
    )

    outline_renderer = OutlineRenderer(token_budget=DEFAULT_OUTLINE_TOKEN_BUDGET)
    outline_text, _scoped_outline = outline_renderer.render(
        codebase_map,
        changed_files,
    )

    model_config = ModelConfig(
        model=model,
        max_tokens=TokenCount(max_tokens),
        temperature=0.0,
    )
    analyzer = LLMPatternAnalyzer(config=model_config)
    profile_service = ProfileService(analyzer=analyzer)

    # Pass existing outline to preserve all entries — the scoped outline
    # is only used for LLM analysis text, not as the new stored outline.
    memory = profile_service.update_profile(
        existing_memory,
        existing_memory.outline,
        outline_text,
    )
    memory = CodebaseMemory(
        repo_id=memory.repo_id,
        outline=memory.outline,
        patterns=memory.patterns,
        version=memory.version,
        analyzed_at=CommitSHA(after_sha),
    )
    memory_store.save(memory)

    logger.info(
        "Pattern analysis complete: %d patterns (version %d)",
        len(memory.patterns),
        memory.version,
    )


def _maybe_build_embeddings(
    storage_dir: Path,
    codebase_map: CodebaseMap,
    changed_files: list[FilePath],
    client: GitHubClient,
    after_sha: str,
) -> None:
    """Build embedding indices for changed shards if embedding_model is configured."""
    embedding_model = os.environ.get("INPUT_EMBEDDING_MODEL", "")
    if not embedding_model:
        return

    from argus.domain.context.value_objects import EmbeddingIndex, ShardId, shard_id_for
    from argus.infrastructure.parsing.chunker import Chunker
    from argus.infrastructure.retrieval.embeddings import create_embedding_provider
    from argus.infrastructure.storage.artifact_store import ShardedArtifactStore

    try:
        provider = create_embedding_provider(embedding_model)
    except Exception:
        logger.warning("Could not create embedding provider, skipping embeddings")
        return

    chunker = Chunker()
    store = ShardedArtifactStore(storage_dir=storage_dir)

    # Determine changed shard IDs.
    changed_shard_ids: set[ShardId] = {shard_id_for(f) for f in changed_files}

    for sid in changed_shard_ids:
        texts: list[str] = []
        chunk_ids: list[str] = []
        for path in codebase_map.files():
            if shard_id_for(path) != sid:
                continue
            if path not in codebase_map:
                continue
            entry = codebase_map.get(path)
            try:
                content = client.get_file_content(path, ref=after_sha)
                file_chunks = chunker.chunk(path, content, entry.symbols)
                for chunk in file_chunks:
                    texts.append(chunk.content)
                    chunk_ids.append(f"{chunk.source}:{chunk.symbol_name}")
            except Exception:
                logger.debug("Could not fetch/chunk %s for embeddings", path)

        if not texts:
            continue

        try:
            embeddings = provider.embed(texts)
            index = EmbeddingIndex(
                shard_id=sid,
                embeddings=embeddings,
                chunk_ids=chunk_ids,
                dimension=provider.dimension,
                model=embedding_model,
            )
            store.save_embedding_index(index)
            logger.info("Built embeddings for shard %s: %d chunks", sid, len(texts))
        except Exception:
            logger.warning("Failed to build embeddings for shard %s", sid)


def _incremental_update_sharded(
    client: GitHubClient,
    parser: TreeSitterParser,
    store: ShardedArtifactStore,
    codebase_map: CodebaseMap,
    repo: str,
    before_sha: str,
    after_sha: str,
    existing_manifest: ShardedManifest | None = None,
) -> list[FilePath]:
    """Update the codebase map and re-shard only dirty directories.

    Returns:
        List of changed source file paths that were updated.
    """
    changed_paths = client.compare_commits(before_sha, after_sha)
    parseable = get_parseable_extensions()
    source_paths = [p for p in changed_paths if _is_parseable(p, parseable)]

    if not source_paths:
        logger.info("No parseable files changed, skipping update")
        return []

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

    return [FilePath(p) for p in source_paths]


if __name__ == "__main__":
    run()
