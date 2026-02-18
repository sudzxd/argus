"""Incremental index command — updates codebase artifacts for changed files only.

On push to main/develop, this entry point:
1. Pulls existing artifacts from the argus-data branch
2. Determines which files changed in the push (via compare API)
3. Incrementally updates the codebase map and memory
4. Pushes updated artifacts back to argus-data

Falls back to a full bootstrap if no existing artifacts are found.

Usage:
    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
    GITHUB_EVENT_PATH=/path/to/push-event.json \
    INPUT_MODEL=google-gla:gemini-2.5-flash \
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
from argus.domain.llm.value_objects import ModelConfig
from argus.domain.memory.services import ProfileService
from argus.infrastructure.constants import DATA_BRANCH
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.storage.artifact_store import FileArtifactStore
from argus.infrastructure.storage.git_branch_store import GitBranchSync
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.interfaces.bootstrap import get_parseable_extensions
from argus.shared.constants import DEFAULT_OUTLINE_TOKEN_BUDGET
from argus.shared.exceptions import ArgusError, ConfigurationError, IndexingError
from argus.shared.types import CommitSHA, FilePath, TokenCount

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
    """Incremental index: update artifacts for changed files only."""
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
    model = os.environ.get("INPUT_MODEL", "google-gla:gemini-2.5-flash")
    max_tokens = int(os.environ.get("INPUT_MAX_TOKENS", "1000000"))
    storage_dir = Path(os.environ.get("INPUT_STORAGE_DIR", ".argus-artifacts"))

    client = GitHubClient(token=token, repo=repo)
    parser = TreeSitterParser()
    store = FileArtifactStore(storage_dir=storage_dir)
    memory_store = FileMemoryStore(storage_dir=storage_dir)
    sync = GitBranchSync(client=client, branch=DATA_BRANCH, storage_dir=storage_dir)

    # 1. Pull existing artifacts.
    sync.pull()
    existing_map = store.load(repo)

    if existing_map is None:
        # No existing artifacts — delegate to full bootstrap.
        logger.info("No existing codebase map, falling back to full bootstrap")
        from argus.interfaces.bootstrap import run as bootstrap_run

        bootstrap_run()
    else:
        # Incremental update — only process changed files.
        before_sha, after_sha = _extract_push_shas(event_path)
        _incremental_update(
            client,
            parser,
            store,
            memory_store,
            existing_map,
            repo,
            model,
            max_tokens,
            before_sha,
            after_sha,
        )

    # 2. Push updated artifacts.
    sync.push()


def _incremental_update(
    client: GitHubClient,
    parser: TreeSitterParser,
    store: FileArtifactStore,
    memory_store: FileMemoryStore,
    codebase_map: CodebaseMap,
    repo: str,
    model: str,
    max_tokens: int,
    before_sha: str,
    after_sha: str,
) -> None:
    """Update the codebase map with only the files changed between two commits."""
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

    # Update the indexed_at SHA (CodebaseMap is not frozen).
    codebase_map.indexed_at = CommitSHA(after_sha)

    logger.info("Updated %d files in codebase map", updated)
    store.save(repo, codebase_map)

    # Rebuild memory profile with updated map.
    _rebuild_memory(memory_store, codebase_map, repo, model, max_tokens)


def _rebuild_memory(
    memory_store: FileMemoryStore,
    codebase_map: CodebaseMap,
    repo: str,
    model: str,
    max_tokens: int,
) -> None:
    """Render outline and build/update memory profile."""
    outline_renderer = OutlineRenderer(token_budget=DEFAULT_OUTLINE_TOKEN_BUDGET)
    outline_text, outline = outline_renderer.render_full(codebase_map)

    model_config = ModelConfig(
        model=model,
        max_tokens=TokenCount(max_tokens),
        temperature=0.0,
    )
    analyzer = LLMPatternAnalyzer(config=model_config)
    profile_service = ProfileService(analyzer=analyzer)

    existing_memory = memory_store.load(repo)
    if existing_memory is not None:
        logger.info("Updating existing codebase memory profile...")
        memory = profile_service.update_profile(existing_memory, outline, outline_text)
    else:
        logger.info("Building new codebase memory profile...")
        memory = profile_service.build_profile(repo, outline, outline_text)

    memory_store.save(memory)

    logger.info(
        "Index complete: %d files, %d patterns (version %d)",
        memory.outline.file_count,
        len(memory.patterns),
        memory.version,
    )


if __name__ == "__main__":
    run()
