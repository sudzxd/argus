# Interfaces Layer (Composition Root)

> Inherits all rules from root `CLAUDE.md`.

The only layer that imports from all other layers. Wires infrastructure into application use cases.

## Modules

| File | What it does |
|------|-------------|
| `config.py` | `ActionConfig.from_env()` — reads `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_EVENT_PATH` + optional `INPUT_*` env vars |
| `review_generator.py` | `LLMReviewGenerator` — bridges `ReviewGeneratorPort` to pydantic-ai `Agent` with `ReviewOutput` structured schema |
| `action.py` | `run()` entry point — parses GitHub event, constructs all infrastructure, wires use case, executes pipeline |

## Data Flow

```
action.py::run()
  → ActionConfig.from_env()           # read config
  → _load_event()                     # parse GitHub webhook payload
  → GitHubClient.get_pull_request_diff()
  → TreeSitterParser + Chunker        # build codebase map + chunks
  → RetrievalOrchestrator             # structural + lexical + optional agentic
  → LLMReviewGenerator.generate()     # LLM structured review
  → NoiseFilter                       # drop low-confidence / ignored paths
  → GitHubReviewPublisher             # post inline PR comments
```

## Environment Variables

See `.env.example` for all variables. Key ones:
- `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_EVENT_PATH` (required)
- `INPUT_MODEL`, `INPUT_MAX_TOKENS`, `INPUT_TEMPERATURE` (optional, with defaults)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (provider-specific)
