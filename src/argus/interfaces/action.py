"""GitHub Action entry point — composition root."""

from __future__ import annotations

import json
import logging
import sys

from pathlib import Path
from typing import cast

import httpx

from argus.application.dto import ReviewPullRequestCommand
from argus.application.review_pull_request import ReviewPullRequest
from argus.domain.context.services import IndexingService
from argus.domain.llm.value_objects import ModelConfig, TokenBudget
from argus.domain.memory.services import ProfileService
from argus.domain.retrieval.services import RetrievalOrchestrator
from argus.domain.retrieval.strategies import RetrievalStrategy
from argus.domain.review.services import NoiseFilter
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.github.publisher import GitHubReviewPublisher
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.infrastructure.parsing.chunker import Chunker, CodeChunk
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.retrieval.agentic import AgenticRetrievalStrategy
from argus.infrastructure.retrieval.lexical import LexicalRetrievalStrategy
from argus.infrastructure.retrieval.structural import StructuralRetrievalStrategy
from argus.infrastructure.storage.artifact_store import FileArtifactStore
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.interfaces.config import ActionConfig
from argus.interfaces.review_generator import LLMReviewGenerator
from argus.shared.constants import (
    DEFAULT_GENERATION_BUDGET_RATIO,
    DEFAULT_OUTLINE_TOKEN_BUDGET,
    DEFAULT_RETRIEVAL_BUDGET_RATIO,
)
from argus.shared.exceptions import ArgusError, IndexingError
from argus.shared.types import CommitSHA, FilePath, ReviewDepth, TokenCount

logger = logging.getLogger(__name__)


def run() -> None:
    """Execute the Argus PR review pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        config = ActionConfig.from_env()
        _execute_pipeline(config)
    except ArgusError as e:
        logger.error("Argus failed: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error")
        sys.exit(1)


def _execute_pipeline(config: ActionConfig) -> None:
    """Wire infrastructure, build use case, and execute."""
    # 1. Parse event
    event = _load_event(config.github_event_path)
    pr_number = _extract_pr_number(event)
    head_sha = CommitSHA(_extract_head_sha(event))

    # 2. Construct infrastructure
    client = GitHubClient(token=config.github_token, repo=config.github_repository)
    parser = TreeSitterParser()
    chunker = Chunker()
    store = FileArtifactStore(storage_dir=Path(config.storage_dir))
    # 3. Fetch PR data
    diff = client.get_pull_request_diff(pr_number)
    publisher = GitHubReviewPublisher(client=client, diff=diff)
    changed_files = _extract_changed_files(diff)

    file_contents: dict[FilePath, str] = {}
    for path in changed_files:
        try:
            content = client.get_file_content(path, ref=head_sha)
            file_contents[path] = content
        except (ArgusError, httpx.HTTPError) as e:
            logger.warning("Could not fetch %s, skipping: %s", path, e)

    # 4. Build codebase map for structural retrieval
    existing_map = store.load(config.github_repository)
    if existing_map is not None:
        codebase_map = existing_map
    else:
        from argus.domain.context.entities import CodebaseMap

        codebase_map = CodebaseMap(indexed_at=head_sha)

    for path, content in file_contents.items():
        try:
            entry = parser.parse(path, content)
            codebase_map.upsert(entry)
        except (IndexingError, ArgusError) as e:
            logger.debug("Skipping unparseable file for retrieval: %s (%s)", path, e)

    # 5. Build chunks for lexical retrieval
    chunks: list[CodeChunk] = []
    for path, content in file_contents.items():
        if path in codebase_map:
            entry = codebase_map.get(path)
            chunks.extend(chunker.chunk(path, content, entry.symbols))

    # 6. Build retrieval strategies
    model_config = ModelConfig(
        model=config.model,
        max_tokens=TokenCount(config.max_tokens),
        temperature=config.temperature,
    )
    token_budget = TokenBudget(
        total=TokenCount(config.max_tokens),
        retrieval_ratio=DEFAULT_RETRIEVAL_BUDGET_RATIO,
        generation_ratio=DEFAULT_GENERATION_BUDGET_RATIO,
    )

    strategies: list[RetrievalStrategy] = [
        StructuralRetrievalStrategy(codebase_map=codebase_map),
        LexicalRetrievalStrategy(chunks=chunks),
    ]

    if config.enable_agentic:
        strategies.append(
            AgenticRetrievalStrategy(
                config=model_config,
                fallback_strategies=[strategies[1]],  # lexical as fallback
            )
        )

    orchestrator = RetrievalOrchestrator(
        strategies=strategies,
        budget=token_budget.retrieval_tokens,
    )

    # 7. Wire review generator + noise filter
    review_generator = LLMReviewGenerator(config=model_config)
    noise_filter = NoiseFilter(
        confidence_threshold=config.confidence_threshold,
        ignored_paths=[FilePath(p) for p in config.ignored_paths],
    )

    # 8. Wire memory components (based on review depth)
    outline_renderer = None
    memory_store = None
    profile_service = None

    if config.review_depth != ReviewDepth.QUICK:
        outline_renderer = OutlineRenderer(
            token_budget=DEFAULT_OUTLINE_TOKEN_BUDGET,
        )

        if config.review_depth == ReviewDepth.DEEP:
            memory_store = FileMemoryStore(
                storage_dir=Path(config.storage_dir),
            )
            analyzer = LLMPatternAnalyzer(config=model_config)
            profile_service = ProfileService(analyzer=analyzer)

    # 9. Wire use case
    indexing_service = IndexingService(parser=parser, repository=store)
    use_case = ReviewPullRequest(
        indexing_service=indexing_service,
        repository=store,
        orchestrator=orchestrator,
        review_generator=review_generator,
        noise_filter=noise_filter,
        publisher=publisher,
        outline_renderer=outline_renderer,
        memory_repository=memory_store,
        profile_service=profile_service,
    )

    # 10. Execute
    cmd = ReviewPullRequestCommand(
        repo_id=config.github_repository,
        pr_number=pr_number,
        commit_sha=head_sha,
        diff=diff,
        changed_files=changed_files,
        file_contents=file_contents,
        review_depth=config.review_depth,
    )

    result = use_case.execute(cmd)
    logger.info(
        "Review complete: %d comments, %d context items, %d tokens used",
        len(result.review),
        result.context_items_used,
        result.tokens_used,
    )


def _load_event(event_path: str) -> dict[str, object]:
    """Load the GitHub event JSON file."""
    with Path(event_path).open() as f:
        result: dict[str, object] = json.load(f)
        return result


def _extract_pr_number(event: dict[str, object]) -> int:
    """Extract PR number from event payload."""
    pr: object = event.get("pull_request", event.get("number"))
    if isinstance(pr, dict):
        pr_data = cast(dict[str, object], pr)
        number: object = pr_data.get("number")
        if isinstance(number, int):
            return number
        msg = "Cannot extract PR number from event payload"
        raise ValueError(msg)
    if isinstance(pr, int):
        return pr
    msg = "Cannot extract PR number from event payload"
    raise ValueError(msg)


def _extract_head_sha(event: dict[str, object]) -> str:
    """Extract head commit SHA from event payload."""
    pr: object = event.get("pull_request")
    if not isinstance(pr, dict):
        msg = "Cannot extract head SHA from event payload"
        raise ValueError(msg)
    pr_data = cast(dict[str, object], pr)
    head: object = pr_data.get("head")
    if not isinstance(head, dict):
        msg = "Cannot extract head SHA from event payload"
        raise ValueError(msg)
    head_data = cast(dict[str, object], head)
    sha: object = head_data.get("sha")
    if isinstance(sha, str):
        return sha
    msg = "Cannot extract head SHA from event payload"
    raise ValueError(msg)


def _extract_changed_files(diff: str) -> list[FilePath]:
    """Parse file paths from a unified diff."""
    files: list[FilePath] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            files.append(FilePath(path))
    return files


if __name__ == "__main__":
    run()
