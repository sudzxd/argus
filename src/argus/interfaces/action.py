"""GitHub Action entry point — composition root."""

from __future__ import annotations

import json
import logging
import sys

from pathlib import Path, PurePosixPath
from posixpath import normpath
from typing import cast

import httpx

from argus.application.dto import ReviewPullRequestCommand
from argus.application.review_pull_request import ReviewPullRequest
from argus.domain.context.entities import CodebaseMap
from argus.domain.context.services import IndexingService
from argus.domain.context.value_objects import ShardId
from argus.domain.llm.value_objects import LLMUsage, ModelConfig, TokenBudget
from argus.domain.memory.services import ProfileService
from argus.domain.retrieval.services import RetrievalOrchestrator
from argus.domain.retrieval.strategies import RetrievalStrategy
from argus.domain.review.services import NoiseFilter
from argus.domain.review.value_objects import PRContext
from argus.infrastructure.constants import DATA_BRANCH
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.github.pr_context_collector import PRContextCollector
from argus.infrastructure.github.publisher import GitHubReviewPublisher
from argus.infrastructure.memory.llm_analyzer import LLMPatternAnalyzer
from argus.infrastructure.memory.outline_renderer import OutlineRenderer
from argus.infrastructure.parsing.chunker import Chunker, CodeChunk
from argus.infrastructure.parsing.tree_sitter_parser import TreeSitterParser
from argus.infrastructure.retrieval.agentic import AgenticRetrievalStrategy
from argus.infrastructure.retrieval.lexical import LexicalRetrievalStrategy
from argus.infrastructure.retrieval.structural import StructuralRetrievalStrategy
from argus.infrastructure.storage.artifact_store import ShardedArtifactStore
from argus.infrastructure.storage.git_branch_store import (
    GitBranchSync,
    SelectiveGitBranchSync,
)
from argus.infrastructure.storage.memory_store import FileMemoryStore
from argus.interfaces.config import ActionConfig
from argus.interfaces.review_generator import LLMReviewGenerator
from argus.shared.constants import (
    AGENTIC_BUDGET_RATIO,
    DEFAULT_GENERATION_BUDGET_RATIO,
    DEFAULT_OUTLINE_TOKEN_BUDGET,
    DEFAULT_RETRIEVAL_BUDGET_RATIO,
    LEXICAL_BUDGET_RATIO,
    SEMANTIC_BUDGET_RATIO,
    STRUCTURAL_BUDGET_RATIO,
)
from argus.shared.exceptions import (
    ArgusError,
    ConfigurationError,
    IndexingError,
    PublishError,
)
from argus.shared.types import CommitSHA, FilePath, ReviewDepth, TokenCount

logger = logging.getLogger(__name__)


def run() -> None:
    """Execute the Argus PR review pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        config = ActionConfig.from_toml()
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
    storage_path = Path(config.storage_dir)
    sharded_store = ShardedArtifactStore(storage_dir=storage_path)

    # 2b. Pull cached artifacts — try selective sharded pull first
    selective_sync = SelectiveGitBranchSync(
        client=client,
        branch=DATA_BRANCH,
        storage_dir=storage_path,
    )

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

    # 3b. Collect PR context (metadata, CI, comments, git health)
    pr_context: PRContext | None = None
    if config.enable_pr_context:
        try:
            collector = PRContextCollector(client=client)
            pr_context = collector.collect(
                pr_number=pr_number,
                head_sha=head_sha,
                search_related=config.search_related_issues,
            )
            logger.info(
                "Collected PR context: CI=%s, %d comments, %d days open",
                pr_context.ci_status.conclusion,
                len(pr_context.comments),
                pr_context.git_health.days_open,
            )
        except Exception:
            logger.warning("Could not collect PR context, continuing without it")

    # 4. Build codebase map — selective shard loading
    codebase_map: CodebaseMap | None = None
    loaded_shard_ids: set[ShardId] = set()
    try:
        has_manifest = selective_sync.pull_manifest()
        if has_manifest:
            manifest = sharded_store.load_manifest(config.github_repository)
            if manifest is not None:
                # Compute which shards we need: changed files + 1-hop neighbors.
                needed = manifest.shards_for_files(changed_files)
                adjacent = manifest.adjacent_shards(needed, hops=1)
                all_needed = needed | adjacent
                blob_names = {
                    manifest.shards[sid].blob_name
                    for sid in all_needed
                    if sid in manifest.shards
                }
                # Also pull memory files (discovered from cached tree).
                memory_blobs = selective_sync.memory_blob_names()
                selective_sync.pull_blobs(blob_names | memory_blobs)
                loaded_shard_ids = all_needed
                codebase_map = sharded_store.load_shards(
                    config.github_repository,
                    all_needed,
                )
                logger.info(
                    "Loaded %d shards (%d needed + %d adjacent)",
                    len(all_needed),
                    len(needed),
                    len(adjacent),
                )
    except PublishError:
        logger.warning("Could not pull sharded artifacts, trying legacy")

    if codebase_map is None:
        # Fallback to legacy full pull.
        legacy_sync = GitBranchSync(
            client=client,
            branch=DATA_BRANCH,
            storage_dir=storage_path,
        )
        try:
            legacy_sync.pull()
        except PublishError:
            logger.warning(
                "Could not pull artifacts from %s, starting fresh",
                DATA_BRANCH,
            )
        existing_map = sharded_store.load_or_migrate(config.github_repository)
        if existing_map is not None:
            codebase_map = existing_map
        else:
            codebase_map = CodebaseMap(indexed_at=head_sha)

    for path, content in file_contents.items():
        try:
            entry = parser.parse(path, content)
            codebase_map.upsert(entry)
        except (IndexingError, ArgusError) as e:
            logger.debug("Skipping unparseable file for retrieval: %s (%s)", path, e)

    # 5. Build chunks for lexical retrieval from context files (non-changed)
    changed_set = set(changed_files)
    context_contents: dict[FilePath, str] = {}
    for path in codebase_map.files():
        if path in changed_set:
            continue
        try:
            content = client.get_file_content(path, ref=head_sha)
            context_contents[path] = content
        except (ArgusError, httpx.HTTPError) as e:
            logger.debug("Could not fetch context file %s: %s", path, e)

    chunks: list[CodeChunk] = []
    for path, content in context_contents.items():
        if path in codebase_map:
            entry = codebase_map.get(path)
            chunks.extend(chunker.chunk(path, content, entry.symbols))

    logger.info(
        "Built %d chunks from %d context files for lexical retrieval",
        len(chunks),
        len(context_contents),
    )

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

    retrieval_budget = token_budget.retrieval_tokens
    strategy_budgets: list[TokenCount] = [
        TokenCount(int(retrieval_budget * STRUCTURAL_BUDGET_RATIO)),
        TokenCount(int(retrieval_budget * LEXICAL_BUDGET_RATIO)),
    ]

    if config.enable_agentic:
        strategies.append(
            AgenticRetrievalStrategy(
                config=model_config,
                fallback_strategies=[strategies[1]],  # lexical as fallback
            )
        )
        strategy_budgets.append(
            TokenCount(int(retrieval_budget * AGENTIC_BUDGET_RATIO)),
        )

    if config.embedding_model:
        try:
            from argus.infrastructure.retrieval.embeddings import (
                create_embedding_provider,
            )
            from argus.infrastructure.retrieval.semantic import (
                SemanticRetrievalStrategy,
            )

            # Pull embedding blobs from remote.
            embedding_blobs = selective_sync.embedding_blob_names()
            if embedding_blobs:
                selective_sync.pull_blobs(embedding_blobs)

            # Load embedding indices for needed shards.
            embedding_indices = sharded_store.load_embedding_indices(
                loaded_shard_ids,
                model=config.embedding_model,
            )
            if embedding_indices:
                emb_provider = create_embedding_provider(config.embedding_model)
                strategies.append(
                    SemanticRetrievalStrategy(
                        provider=emb_provider,
                        embedding_indices=embedding_indices,
                        chunks=chunks,
                    )
                )
                strategy_budgets.append(
                    TokenCount(int(retrieval_budget * SEMANTIC_BUDGET_RATIO)),
                )
                logger.info(
                    "Semantic retrieval enabled with %d embedding indices",
                    len(embedding_indices),
                )
        except Exception:
            logger.warning(
                "Could not initialize semantic retrieval, continuing without it"
            )

    orchestrator = RetrievalOrchestrator(
        strategies=strategies,
        budget=retrieval_budget,
        strategy_budgets=strategy_budgets,
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
    indexing_service = IndexingService(parser=parser, repository=sharded_store)
    use_case = ReviewPullRequest(
        indexing_service=indexing_service,
        repository=sharded_store,
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
        preloaded_map=codebase_map,
        pr_context=pr_context,
    )

    result = use_case.execute(cmd)

    # Aggregate LLM usage: generation + agentic retrieval
    generation_usage = result.llm_usage
    agentic_usage = LLMUsage()
    agentic_strategy: AgenticRetrievalStrategy | None = None
    for strategy in strategies:
        if isinstance(strategy, AgenticRetrievalStrategy):
            agentic_strategy = strategy
            break
    if agentic_strategy is not None:
        agentic_usage = agentic_strategy.last_llm_usage
    total_usage = generation_usage + agentic_usage

    logger.info(
        "Review complete: %d comments, %d context items",
        len(result.review),
        result.context_items_used,
    )
    logger.info(
        "  Retrieval: %d context tokens",
        result.tokens_used,
    )
    logger.info(
        "  LLM API: %d tokens (%d input + %d output) across %d requests",
        total_usage.total_tokens,
        total_usage.input_tokens,
        total_usage.output_tokens,
        total_usage.requests,
    )
    logger.info(
        "    Generation: %d tokens (%d requests)",
        generation_usage.total_tokens,
        generation_usage.requests,
    )
    if agentic_usage.requests > 0:
        logger.info(
            "    Agentic retrieval: %d tokens (%d requests)",
            agentic_usage.total_tokens,
            agentic_usage.requests,
        )


def _load_event(event_path: str) -> dict[str, object]:
    """Load the GitHub event JSON file."""
    try:
        with Path(event_path).open() as f:
            result: dict[str, object] = json.load(f)
            return result
    except FileNotFoundError as e:
        raise ConfigurationError(f"Event file not found: {event_path}") from e
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid event JSON: {e}") from e


def _extract_pr_number(event: dict[str, object]) -> int:
    """Extract PR number from event payload."""
    pr: object = event.get("pull_request", event.get("number"))
    if isinstance(pr, dict):
        pr_data = cast(dict[str, object], pr)
        number: object = pr_data.get("number")
        if isinstance(number, int):
            return number
        msg = "Cannot extract PR number from event payload"
        raise ConfigurationError(msg)
    if isinstance(pr, int):
        return pr
    msg = "Cannot extract PR number from event payload"
    raise ConfigurationError(msg)


def _extract_head_sha(event: dict[str, object]) -> str:
    """Extract head commit SHA from event payload."""
    pr: object = event.get("pull_request")
    if not isinstance(pr, dict):
        msg = "Cannot extract head SHA from event payload"
        raise ConfigurationError(msg)
    pr_data = cast(dict[str, object], pr)
    head: object = pr_data.get("head")
    if not isinstance(head, dict):
        msg = "Cannot extract head SHA from event payload"
        raise ConfigurationError(msg)
    head_data = cast(dict[str, object], head)
    sha: object = head_data.get("sha")
    if isinstance(sha, str):
        return sha
    msg = "Cannot extract head SHA from event payload"
    raise ConfigurationError(msg)


def _extract_changed_files(diff: str) -> list[FilePath]:
    """Parse file paths from a unified diff."""
    files: list[FilePath] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            normalized = normpath(path)
            if normalized.startswith("..") or PurePosixPath(normalized).is_absolute():
                logger.warning("Skipping suspicious path: %s", path)
                continue
            files.append(FilePath(path))
    return files


if __name__ == "__main__":
    run()
