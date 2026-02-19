# Interfaces Layer (Composition Root)

> Inherits all rules from root `CLAUDE.md`.

The only layer that imports from all other layers. Wires infrastructure into application use cases.

## Modules

| File | What it does |
|------|-------------|
| `main.py` | Unified dispatcher — reads `INPUT_MODE` env var, routes to `action`, `sync_index`, or `bootstrap` |
| `config.py` | `ActionConfig.from_env()` — reads `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_EVENT_PATH` + optional `INPUT_*` env vars |
| `review_generator.py` | `LLMReviewGenerator` — bridges `ReviewGeneratorPort` to pydantic-ai `Agent` with `ReviewOutput` structured schema |
| `action.py` | PR review entry point — parses GitHub event, constructs all infrastructure, wires use case, executes review pipeline |
| `bootstrap.py` | Full rebuild — fetches full repo tree, parses all files, builds outline + patterns, sets `analyzed_at` |
| `sync_index.py` | Incremental index on push — updates codebase map for changed files, optionally runs pattern analysis (`INPUT_ANALYZE_PATTERNS`) |
| `sync_push.py` | Push artifacts to `argus-data` branch via Git Data API |

## Data Flow

```
action.py::run()  (review mode)
  → ActionConfig.from_env()           # read config
  → _load_event()                     # parse GitHub webhook payload
  → GitHubClient.get_pull_request_diff()
  → SelectiveGitBranchSync            # pull manifest + needed shards + memory
  → TreeSitterParser + Chunker        # build codebase map + chunks
  → RetrievalOrchestrator             # structural + lexical + optional agentic
  → LLMReviewGenerator.generate()     # LLM structured review
  → NoiseFilter                       # drop low-confidence / ignored paths
  → GitHubReviewPublisher             # post inline PR comments

sync_index.py::run()  (index mode)
  → SelectiveGitBranchSync.pull_manifest()
  → compare_commits(indexed_at, HEAD)
  → pull dirty shards, parse changed files
  → save_incremental() (merge into manifest)
  → [optional] _maybe_analyze_patterns()  # if INPUT_ANALYZE_PATTERNS=true
  → sync.push()

bootstrap.py::run()  (bootstrap mode)
  → fetch full tree, parse all files
  → render outline + analyze patterns via LLM
  → save sharded map + memory (with analyzed_at)
  → sync_push.py pushes to argus-data
```

## Environment Variables

See `.env.example` for all variables. Key ones:
- `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_EVENT_PATH` (required)
- `INPUT_MODEL`, `INPUT_MAX_TOKENS`, `INPUT_TEMPERATURE` (optional, with defaults)
- `INPUT_ANALYZE_PATTERNS` — `"true"` to enable pattern analysis in index mode
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` (provider-specific)
