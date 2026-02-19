# Infrastructure Layer

> Inherits all rules from root `CLAUDE.md`.

Concrete implementations of domain protocols. Imports from `domain/` and `shared/` only.

## Modules

| Module | Implements | How |
|--------|-----------|-----|
| `parsing/tree_sitter_parser.py` | `SourceParser` protocol | Tree-sitter AST parsing for 11 languages |
| `parsing/chunker.py` | — | Splits source files into semantic `CodeChunk`s around symbols |
| `storage/artifact_store.py` | `CodebaseMapRepository` protocol | Sharded JSON persistence (`ShardedArtifactStore`) with legacy flat format fallback (`FileArtifactStore`) |
| `storage/git_branch_store.py` | — | `SelectiveGitBranchSync` (manifest-first pull, selective blob download, base_tree push) and `GitBranchSync` (legacy full pull/push) |
| `storage/memory_store.py` | `CodebaseMemoryRepository` protocol | JSON file persistence with file locking; serializes `analyzed_at` field |
| `retrieval/structural.py` | `RetrievalStrategy` protocol | Graph-walk over `CodebaseMap` symbol dependencies |
| `retrieval/lexical.py` | `RetrievalStrategy` protocol | BM25 sparse retrieval using `bm25s` |
| `retrieval/agentic.py` | `RetrievalStrategy` protocol | LLM-guided iterative retrieval via pydantic-ai `Agent` |
| `llm_providers/factory.py` | — | `create_agent()` builds pydantic-ai `Agent` from `ModelConfig` |
| `github/client.py` | — | GitHub REST API: diffs, file content, PR comments, Git Data API (trees, blobs, commits, refs) |
| `github/publisher.py` | `ReviewPublisher` protocol | Posts `Review` as inline PR comments at diff positions |
| `memory/outline_renderer.py` | `OutlineRendererPort` | Renders codebase outlines within token budget (scoped or full) |
| `memory/llm_analyzer.py` | `PatternAnalyzer` protocol | LLM-based codebase pattern discovery (full and incremental) |

## Rules

- Never import from `application` or `interfaces`.
- Each module satisfies a domain protocol — check `domain/*/repositories.py` and `domain/retrieval/strategies.py` for the contracts.
- Mock external I/O (HTTP, filesystem) in tests.

## LLM Integration

All LLM calls go through **pydantic-ai**. The domain defines `ModelConfig`; the factory creates `Agent` instances. Structured output uses tool-calling mode for cloud providers (Gemini, Claude, OpenAI).

## Storage Architecture

Artifacts live on the `argus-data` orphan branch:
- `manifest.json` — DAG index with shard descriptors + cross-shard edges + `indexed_at`
- `shard_<hash>.json` — one per leaf directory (entries + internal edges)
- `<hash>_memory.json` — patterns + outline + `analyzed_at`

`SelectiveGitBranchSync` caches tree entries after `pull_manifest()` to avoid redundant API calls. `memory_blob_names()` discovers memory files from the cached tree. Push uses `base_tree` for incremental tree updates.
