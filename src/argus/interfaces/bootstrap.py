"""Bootstrap command — builds codebase memory from scratch.

Usage:
    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
    INPUT_MODEL=google-gla:gemini-2.5-flash \
    uv run python -m argus.interfaces.bootstrap
"""

from __future__ import annotations

import logging
import os
import sys

from pathlib import Path

import httpx

from argus.domain.context.entities import CodebaseMap
from argus.domain.llm.value_objects import ModelConfig
from argus.domain.memory.services import ProfileService
from argus.domain.memory.value_objects import CodebaseMemory
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.storage.artifact_store import ShardedArtifactStore
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.interfaces.env_utils import (
    DEFAULT_INDEX_MAX_TOKENS,
    DEFAULT_INDEX_MODEL,
    require_env,
)
from argus.shared.constants import DEFAULT_OUTLINE_TOKEN_BUDGET, MAX_FILE_SIZE_BYTES
from argus.shared.exceptions import ArgusError, IndexingError
from argus.shared.types import CommitSHA, FilePath, TokenCount

logger = logging.getLogger(__name__)

# Default extensions we can parse.
PARSEABLE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".rb",
        ".kt",
        ".kts",
        ".swift",
    }
)


def get_parseable_extensions() -> frozenset[str]:
    """Build the set of parseable extensions, including user extras."""
    raw = os.environ.get("INPUT_EXTRA_EXTENSIONS", "")
    extras: set[str] = set()
    for ext in raw.split(","):
        ext = ext.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        extras.add(ext)
    return PARSEABLE_EXTENSIONS | frozenset(extras)


def run() -> None:
    """Bootstrap codebase memory for a repository."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        _execute_bootstrap()
    except ArgusError as e:
        logger.error("Bootstrap failed: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error")
        sys.exit(1)


def _execute_bootstrap() -> None:
    token = require_env("GITHUB_TOKEN")
    repo = require_env("GITHUB_REPOSITORY")
    model = os.environ.get("INPUT_MODEL", DEFAULT_INDEX_MODEL)
    max_tokens = int(os.environ.get("INPUT_MAX_TOKENS", str(DEFAULT_INDEX_MAX_TOKENS)))
    storage_dir = Path(os.environ.get("INPUT_STORAGE_DIR", ".argus-artifacts"))

    client = GitHubClient(token=token, repo=repo)
    parser = TreeSitterParser()
    sharded_store = ShardedArtifactStore(storage_dir=storage_dir)
    memory_store = FileMemoryStore(storage_dir=storage_dir)

    # 1. Get the default branch SHA and full tree.
    logger.info("Fetching repository tree for %s...", repo)
    head_sha = client.get_repo_default_branch_sha()
    tree_entries = client.get_tree_recursive(head_sha)

    # 2. Filter to parseable source files.
    parseable = get_parseable_extensions()
    source_paths: list[str] = []
    for entry in tree_entries:
        if entry.get("type") != "blob":
            continue
        path = str(entry.get("path", ""))
        size = entry.get("size", 0)
        if isinstance(size, int) and size > MAX_FILE_SIZE_BYTES:
            continue
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext in parseable:
            source_paths.append(path)

    logger.info("Found %d parseable source files", len(source_paths))

    # 3. Fetch file contents and build codebase map.
    codebase_map = CodebaseMap(indexed_at=CommitSHA(head_sha))
    file_contents: dict[FilePath, str] = {}
    fetched = 0

    for path_str in source_paths:
        fp = FilePath(path_str)
        try:
            content = client.get_file_content(fp, ref=head_sha)
            file_contents[fp] = content
            entry = parser.parse(fp, content)
            codebase_map.upsert(entry)
            fetched += 1
        except (ArgusError, IndexingError, httpx.HTTPError) as e:
            logger.debug("Skipping %s: %s", path_str, e)

    logger.info("Parsed %d files into codebase map", fetched)

    # 4. Load existing artifacts before overwriting.
    existing_memory = memory_store.load(repo)
    existing_map = sharded_store.load_or_migrate(repo)

    # 5. Save the new codebase map (sharded format).
    sharded_store.save_full(repo, codebase_map)
    logger.info("Saved codebase map artifact (sharded)")

    # 6. Render outline and build memory profile.
    outline_renderer = OutlineRenderer(token_budget=DEFAULT_OUTLINE_TOKEN_BUDGET)

    model_config = ModelConfig(
        model=model,
        max_tokens=TokenCount(max_tokens),
        temperature=0.0,
    )
    analyzer = LLMPatternAnalyzer(config=model_config)
    profile_service = ProfileService(analyzer=analyzer)

    logger.info("Analyzing codebase patterns...")
    if existing_memory is not None and existing_map is not None:
        # Incremental: only analyze changed files for new patterns.
        # Use analyzed_at (last pattern analysis SHA) if available,
        # falling back to indexed_at for backwards compatibility.
        prev_sha = existing_memory.analyzed_at or existing_map.indexed_at
        changed_paths = client.compare_commits(prev_sha, head_sha)
        changed_files = [FilePath(p) for p in changed_paths]
        logger.info(
            "Found existing memory (version %d, %d patterns), "
            "analyzing %d changed files incrementally",
            existing_memory.version,
            len(existing_memory.patterns),
            len(changed_files),
        )
        # Always render the full outline for storage.
        _full_text, full_outline = outline_renderer.render_full(codebase_map)
        if changed_files:
            # Scoped outline text for LLM analysis; full outline for storage.
            outline_text, _scoped = outline_renderer.render(
                codebase_map,
                changed_files,
            )
            memory = profile_service.update_profile(
                existing_memory,
                full_outline,
                outline_text,
            )
        else:
            logger.info("No files changed, keeping existing patterns")
            memory = CodebaseMemory(
                repo_id=existing_memory.repo_id,
                outline=full_outline,
                patterns=existing_memory.patterns,
                version=existing_memory.version,
            )
    else:
        # Fresh: analyze the full codebase.
        outline_text, outline = outline_renderer.render_full(codebase_map)
        memory = profile_service.build_profile(repo, outline, outline_text)

    # Stamp analyzed_at so index mode knows where to diff from.
    memory = CodebaseMemory(
        repo_id=memory.repo_id,
        outline=memory.outline,
        patterns=memory.patterns,
        version=memory.version,
        analyzed_at=CommitSHA(head_sha),
    )
    memory_store.save(memory)

    # 7. Optionally build embedding indices.
    embedding_model = os.environ.get("INPUT_EMBEDDING_MODEL", "")
    if embedding_model:
        _build_embeddings(
            embedding_model=embedding_model,
            codebase_map=codebase_map,
            file_contents=file_contents,
            sharded_store=sharded_store,
        )

    logger.info(
        "Bootstrap complete: %d files, %d patterns (version %d)",
        memory.outline.file_count,
        len(memory.patterns),
        memory.version,
    )


def _build_embeddings(
    embedding_model: str,
    codebase_map: CodebaseMap,
    file_contents: dict[FilePath, str],
    sharded_store: ShardedArtifactStore,
) -> None:
    """Build embedding indices for all shards."""
    from argus.domain.context.value_objects import EmbeddingIndex, ShardId, shard_id_for
    from argus.infrastructure.parsing.chunker import Chunker
    from argus.infrastructure.retrieval.embeddings import create_embedding_provider

    try:
        provider = create_embedding_provider(embedding_model)
    except Exception:
        logger.warning("Could not create embedding provider, skipping embeddings")
        return

    chunker = Chunker()

    # Group files by shard.
    shard_files: dict[ShardId, list[FilePath]] = {}
    for path in codebase_map.files():
        sid = shard_id_for(path)
        shard_files.setdefault(sid, []).append(path)

    built = 0
    for sid, paths in shard_files.items():
        texts: list[str] = []
        chunk_ids: list[str] = []

        for path in paths:
            content = file_contents.get(path)
            if content is None or path not in codebase_map:
                continue
            entry = codebase_map.get(path)
            file_chunks = chunker.chunk(path, content, entry.symbols)
            for chunk in file_chunks:
                texts.append(chunk.content)
                chunk_ids.append(f"{chunk.source}:{chunk.symbol_name}")

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
            sharded_store.save_embedding_index(index)
            built += 1
        except Exception:
            logger.warning("Failed to build embeddings for shard %s", sid)

    logger.info("Built embeddings for %d shards", built)


if __name__ == "__main__":
    run()
