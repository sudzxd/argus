# Tests

> Inherits all rules from root `CLAUDE.md`.

## Structure

```
tests/
├── unit/
│   ├── shared/          # Pure type/exception tests — no mocks
│   ├── domain/          # Pure domain logic — no mocks
│   ├── application/     # Mock all infrastructure behind domain protocols
│   ├── infrastructure/  # Mock external I/O (HTTP, filesystem, LLM)
│   └── interfaces/      # Mock pydantic-ai agent
├── integration/         # Real internal wiring, mock only GitHub API + LLM
├── smoke/               # Live LLM provider tests (skipped without API keys)
│   └── test_providers.py    # Anthropic, OpenAI, local model tests
└── conftest.py
```

## Mocking Strategy

| Test type | What's mocked | What's real |
|-----------|--------------|------------|
| Domain | Nothing | Everything |
| Application | All infrastructure (parser, store, retrieval, publisher) | Domain logic, use case orchestration |
| Infrastructure | HTTP calls, filesystem | Implementation logic |
| Interfaces (unit) | `create_agent` (pydantic-ai) | Config parsing, output mapping |
| Integration | GitHub API + LLM calls | Parser, chunker, storage, retrieval, noise filter, publisher |
| Smoke | Nothing | Full LLM round-trip (requires API keys or local model) |

## Running Smoke Tests

```bash
# Local model (LM Studio/Ollama)
LOCAL_MODEL=qwen/qwen3-coder-30b LOCAL_BASE_URL=http://localhost:1234/v1 make test-smoke

# Anthropic / OpenAI (when keys available)
ANTHROPIC_API_KEY=<key> make test-smoke
OPENAI_API_KEY=<key> make test-smoke
```
