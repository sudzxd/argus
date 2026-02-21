# Interfaces Layer (Composition Root)

> Inherits all rules from root `CLAUDE.md`.

The only layer that imports from all other layers. Wires infrastructure into application use cases.

## Modules

| File | What it does |
|------|-------------|
| `main.py` | Unified dispatcher — reads `INPUT_MODE` env var, routes to `action`, `sync_index`, or `bootstrap` |
| `toml_config.py` | `ArgusConfig` dataclass + `load_argus_config(mode)` — reads `[tool.argus]` from `pyproject.toml` |
| `config.py` | `ActionConfig.from_toml()` — merges TOML config with GitHub runtime env vars (`GITHUB_TOKEN`, etc.) |
| `review_generator.py` | `LLMReviewGenerator` — bridges `ReviewGeneratorPort` to pydantic-ai `Agent` with `ReviewOutput` structured schema |
| `action.py` | PR review entry point — parses GitHub event, constructs all infrastructure, wires use case, executes review pipeline |
| `bootstrap.py` | Full rebuild — fetches full repo tree, parses all files, builds outline + patterns, sets `analyzed_at` |
| `sync_index.py` | Incremental index on push — updates codebase map for changed files, optionally runs pattern analysis |
| `env_utils.py` | `require_env()` shared helper for GitHub runtime env vars and secrets |
| `sync_push.py` | Push artifacts to `argus-data` branch via Git Data API |

## Configuration

All Argus config lives in `[tool.argus]` in `pyproject.toml`:

```toml
[tool.argus]
model = "google-gla:gemini-2.5-flash"
max_tokens = 1000000
storage_dir = ".argus-artifacts"
embedding_model = "local:all-MiniLM-L6-v2"
search_related_issues = true

[tool.argus.index]
model = "google-gla:gemini-2.5-flash"
max_tokens = 1000000
analyze_patterns = true
```

Missing file or missing section → all defaults apply.

### Remaining Environment Variables

Only secrets and GitHub runtime vars stay as env vars:
- `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_EVENT_PATH` (required)
- `INPUT_MODE` (action dispatcher: `review`, `index`, `bootstrap`)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` (provider-specific secrets)

## Data Flow

```
action.py::run()  (review mode)
  → ActionConfig.from_toml()            # read config from pyproject.toml + env secrets
  → _load_event()                       # parse GitHub webhook payload
  → GitHubClient.get_pull_request_diff()
  → PRContextCollector.collect()        # PR metadata, CI, comments, git health
  → SelectiveGitBranchSync              # pull manifest + needed shards + memory + embeddings
  → TreeSitterParser + Chunker          # build codebase map + chunks
  → RetrievalOrchestrator               # structural + lexical + semantic + optional agentic
  → LLMReviewGenerator.generate()       # LLM structured review (diff + PR context + context)
  → NoiseFilter                         # drop low-confidence / ignored paths
  → GitHubReviewPublisher               # post inline PR comments

sync_index.py::run()  (index mode)
  → load_argus_config("index")
  → SelectiveGitBranchSync.pull_manifest()
  → compare_commits(indexed_at, HEAD)
  → pull dirty shards, parse changed files
  → save_incremental() (merge into manifest)
  → [optional] _maybe_analyze_patterns()  # if analyze_patterns = true
  → [optional] _maybe_build_embeddings()  # if embedding_model set
  → sync.push()

bootstrap.py::run()  (bootstrap mode)
  → load_argus_config("bootstrap")
  → fetch full tree, parse all files
  → render outline + analyze patterns via LLM
  → [optional] build embedding indices   # if embedding_model set
  → save sharded map + memory (with analyzed_at)
  → sync_push.py pushes to argus-data
```
