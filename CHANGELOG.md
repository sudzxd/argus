# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **238 tests, 91% coverage** — Unit, integration, and smoke test suites with
  strict markers and coverage enforcement
