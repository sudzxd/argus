# Argus

**AI-powered pull request reviews that understand your codebase.**

---

## The Problem

Code review is one of the most important parts of the development process — and one of the most neglected by current tooling. Existing AI review tools treat every pull request as an isolated diff. They scan line-by-line, flag surface-level style issues, and miss what actually matters: whether the change makes sense in the context of *your* codebase.

They don't know your architecture. They don't know your patterns. They don't know that the function being modified is called by three critical services, or that a similar bug was introduced and fixed two months ago.

## What Argus Does

Argus is a GitHub Action that reviews pull requests with deep understanding of your codebase.

It builds and maintains a semantic map of your repository — the structure, the dependencies, the patterns, the intent behind the code. When a pull request is opened, Argus doesn't just read the diff. It understands what changed, why it matters, and what it affects.

Reviews are posted directly on the pull request as inline comments: a summary of findings, annotations on specific lines, and actionable suggestions — not noise.

## How It Works

Argus operates in three modes:

- **bootstrap** — Parses every file, builds a full codebase map and memory profile (patterns, conventions), shards the map per directory, and stores artifacts on a dedicated `argus-data` branch.
- **index** — Runs on each push to your default branch. Pulls only the manifest and dirty shards, incrementally updates the codebase map for changed files. Optionally runs incremental pattern analysis on changed files when `INPUT_ANALYZE_PATTERNS` is `"true"`.
- **review** — Runs on pull requests. Pulls the manifest, loads only the shards relevant to the changed files (plus 1-hop dependency neighbors), retrieves context, generates a structured review via LLM, and posts inline PR comments.

Artifacts are persisted on an orphan `argus-data` branch using the Git Data API — no databases, no external storage. The codebase map is sharded per directory so that large monorepos only load the slices they need.

## Key Capabilities

- **Codebase-aware reviews** — Every review is grounded in the full context of your repository, not just the changed lines.
- **Smart retrieval** — Hybrid retrieval combining structural analysis (dependency graph), lexical search (BM25), and optional LLM-driven agentic search.
- **Codebase memory** — Learns your project's patterns, conventions, and architectural decisions. Reviews enforce what it knows about your codebase.
- **Multi-provider LLM support** — Bring your own model. Supports Anthropic (Claude), OpenAI, Google (Gemini), and any OpenAI-compatible endpoint.
- **Sharded storage** — The codebase map is split into per-directory shards with a DAG manifest tracking cross-shard dependencies. Reviews and index updates load only the shards they need.
- **Incremental indexing** — The codebase map updates incrementally on each push, with optional pattern analysis on changed files. Bootstrap only runs once (or on demand).
- **Zero infrastructure** — No databases, no servers, no external services beyond the LLM API. Everything runs inside GitHub Actions.

## Configuration

| Input | Default | Description |
|-------|---------|-------------|
| `mode` | `review` | Operating mode: `review`, `index`, or `bootstrap` |
| `model` | `anthropic:claude-sonnet-4-5-20250929` | LLM model identifier |
| `confidence_threshold` | `0.7` | Minimum confidence for review comments |
| `review_depth` | `standard` | `quick` (no memory), `standard` (outline), `deep` (outline + patterns) |
| `ignored_paths` | `""` | Comma-separated glob patterns to ignore |
| `enable_agentic` | `false` | Enable LLM-driven agentic retrieval |
| `extra_extensions` | `""` | Extra file extensions to parse (e.g. `.vue,.svelte`) |
| `analyze_patterns` | `false` | Run incremental pattern analysis during index mode |

## Status

363 tests passing, 80% coverage. All layers implemented and running in CI.

---

*Named after Argus Panoptes — the many-eyed giant of Greek mythology.*
