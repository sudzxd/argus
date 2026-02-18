# Infrastructure Layer

> Inherits all rules from root `CLAUDE.md`.

Concrete implementations of domain protocols. Imports from `domain/` and `shared/` only.

## Modules

| Module | Implements | How |
|--------|-----------|-----|
| `parsing/tree_sitter_parser.py` | `SourceParser` protocol | Tree-sitter AST parsing for 11 languages |
| `parsing/chunker.py` | — | Splits source files into semantic `CodeChunk`s around symbols |
| `storage/artifact_store.py` | `CodebaseMapRepository` protocol | JSON file persistence via `serializer.py` |
| `retrieval/structural.py` | `RetrievalStrategy` protocol | Graph-walk over `CodebaseMap` symbol dependencies |
| `retrieval/lexical.py` | `RetrievalStrategy` protocol | BM25 sparse retrieval using `bm25s` |
| `retrieval/agentic.py` | `RetrievalStrategy` protocol | LLM-guided iterative retrieval via pydantic-ai `Agent` |
| `retrieval/semantic.py` | — | Placeholder for embedding-based retrieval (not yet implemented) |
| `llm_providers/factory.py` | — | `create_agent()` builds pydantic-ai `Agent` from `ModelConfig` |
| `github/client.py` | — | GitHub REST API: diffs, file content, PR comments, tree API |
| `github/publisher.py` | `ReviewPublisher` protocol | Posts `Review` as inline PR comments |
| `memory/outline_renderer.py` | `OutlineRendererPort` | Renders codebase outlines within token budget |
| `memory/llm_analyzer.py` | `PatternAnalyzer` protocol | LLM-based codebase pattern discovery |
| `storage/memory_store.py` | `CodebaseMemoryRepository` protocol | JSON file persistence with file locking |

## Rules

- Never import from `application` or `interfaces`.
- Each module satisfies a domain protocol — check `domain/*/repositories.py` and `domain/retrieval/strategies.py` for the contracts.
- Mock external I/O (HTTP, filesystem) in tests.

## LLM Integration

All LLM calls go through **pydantic-ai**. The domain defines `ModelConfig`; the factory creates `Agent` instances. Structured output uses tool-calling mode for cloud providers (Gemini, Claude, OpenAI).
