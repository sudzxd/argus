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
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.storage.artifact_store import FileArtifactStore
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.shared.constants import DEFAULT_OUTLINE_TOKEN_BUDGET, MAX_FILE_SIZE_BYTES
from argus.shared.exceptions import ArgusError, ConfigurationError, IndexingError
from argus.shared.types import CommitSHA, FilePath, TokenCount

logger = logging.getLogger(__name__)

# Default extensions we can parse.
_DEFAULT_EXTENSIONS = frozenset(
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


def _get_parseable_extensions() -> frozenset[str]:
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
    return _DEFAULT_EXTENSIONS | frozenset(extras)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(f"Missing required env var: {name}")
    return value


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
    token = _require_env("GITHUB_TOKEN")
    repo = _require_env("GITHUB_REPOSITORY")
    model = os.environ.get("INPUT_MODEL", "google-gla:gemini-2.5-flash")
    max_tokens = int(os.environ.get("INPUT_MAX_TOKENS", "1000000"))
    storage_dir = Path(os.environ.get("INPUT_STORAGE_DIR", ".argus-artifacts"))

    client = GitHubClient(token=token, repo=repo)
    parser = TreeSitterParser()
    store = FileArtifactStore(storage_dir=storage_dir)
    memory_store = FileMemoryStore(storage_dir=storage_dir)

    # 1. Get the default branch SHA and full tree.
    logger.info("Fetching repository tree for %s...", repo)
    head_sha = client.get_repo_default_branch_sha()
    tree_entries = client.get_tree_recursive(head_sha)

    # 2. Filter to parseable source files.
    parseable = _get_parseable_extensions()
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

    # 4. Save codebase map.
    store.save(repo, codebase_map)
    logger.info("Saved codebase map artifact")

    # 5. Render outline and build memory profile.
    outline_renderer = OutlineRenderer(token_budget=DEFAULT_OUTLINE_TOKEN_BUDGET)
    outline_text, outline = outline_renderer.render_full(codebase_map)

    model_config = ModelConfig(
        model=model,
        max_tokens=TokenCount(max_tokens),
        temperature=0.0,
    )
    analyzer = LLMPatternAnalyzer(config=model_config)
    profile_service = ProfileService(analyzer=analyzer)

    logger.info("Analyzing codebase patterns...")
    memory = profile_service.build_profile(repo, outline, outline_text)
    memory_store.save(memory)

    logger.info(
        "Bootstrap complete: %d files, %d patterns (version %d)",
        memory.outline.file_count,
        len(memory.patterns),
        memory.version,
    )


if __name__ == "__main__":
    run()
