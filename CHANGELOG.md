# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-19

### Added

- **Incremental pattern analysis in index mode** — Index mode can now
  optionally run LLM-based pattern analysis on changed files after
  updating the codebase map. Controlled by the `INPUT_ANALYZE_PATTERNS`
  env var (default `"false"`). When enabled, index pulls existing memory,
  runs incremental analysis scoped to changed files, and pushes updated
  patterns alongside the codebase map.
- **`analyzed_at` field on `CodebaseMemory`** — Tracks the last commit
  SHA where patterns were analyzed, independent of `indexed_at`. Prevents
  history divergence between index and bootstrap modes.
- **Sharded artifact storage** — Codebase map is split into per-directory
  shards with a DAG manifest (`manifest.json`) on the `argus-data` branch.
  Selective loading ensures reviews and index updates only fetch needed shards.
- **`SelectiveGitBranchSync`** — Manifest-first pull with tree caching,
  selective blob download, and incremental push via `base_tree` merge.
- **LLM usage tracking** — `LLMUsage` value object tracks token counts
  and request counts per strategy; reported in review logs.

### Fixed

- **Outline preservation during incremental analysis** — `update_profile`
  was replacing the full stored outline (all files) with a scoped outline
  (only changed files), causing `memory.json` to lose most outline entries.
  Now the scoped outline text is only used for LLM analysis while the
  full/existing outline is preserved in storage.
- **Bootstrap diff base** — Bootstrap's incremental path now uses
  `analyzed_at` (falling back to `indexed_at`) as the diff base for
  pattern analysis, so it correctly covers all changes since the last
  analysis rather than since the last index.

### Changed

- **CI workflow** — `argus-index.yml` incremental index step now sets
  `INPUT_ANALYZE_PATTERNS: "true"` to enable pattern analysis on push.

## [0.1.0] - 2026-02-17

First release. Argus reviews pull requests with full codebase understanding
and posts structured inline comments.

### Added

- **GitHub Action** (`action.yml`, `Dockerfile`) — Docker-based action with
  configurable model, token budget, confidence threshold, and ignored paths
- **Codebase parsing** — Tree-sitter AST parsing for 11 languages (Python,
  JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, Kotlin, Swift) with
  semantic symbol extraction and code chunking
- **Persistent codebase map** — Incrementally updated `CodebaseMap` with
  dependency graph, stored as JSON artifacts between runs
- **Three retrieval strategies**:
  - Structural: graph-walk over symbol dependencies/dependents
  - Lexical: BM25 sparse retrieval over code chunks (`bm25s`)
  - Agentic: LLM-guided iterative context discovery via pydantic-ai
- **LLM-powered review generation** — Structured `ReviewOutput` schema with
  file, line range, severity, category, confidence, and suggestion fields
- **Noise filtering** — Drops low-confidence comments and comments on ignored
  paths before publishing
- **Inline PR comments** — Posts review comments on specific diff lines with
  severity labels via GitHub REST API
- **Multi-provider LLM support** — Any provider supported by pydantic-ai
  (Anthropic, OpenAI, Google, Groq, local OpenAI-compatible endpoints)
- **CI workflow** (`.github/workflows/ci.yml`) — Lint, typecheck, and test
  on push to main and PRs using `uv`
- **Smoke tests** — Live provider tests for Anthropic, OpenAI, and local models
  (LM Studio/Ollama); skipped when API keys are absent
- **363 tests, 80% coverage** — Unit, integration, and smoke test suites with
  strict markers and coverage enforcement
