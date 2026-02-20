# Argus — AI-Powered Pull Request Reviewer

## Project Identity

Argus is a GitHub Action that reviews pull requests with full codebase understanding.
It parses codebases into semantic maps, retrieves relevant context for each diff,
generates structured reviews via LLM, and posts inline PR comments.

**Reference docs:**
- [`docs/architecture.md`](docs/architecture.md) — bounded contexts, data flow, module structure
- [`docs/style-guide.md`](docs/style-guide.md) — Python conventions, module layout, testing

## Architecture

```
src/argus/
├── shared/           # Foundation kernel — types, exceptions, constants
├── domain/           # Pure domain logic — depends only on shared/
│   ├── context/      # Codebase map: entities, indexing, parsing protocols
│   ├── retrieval/    # Context retrieval: strategies, ranker, orchestrator
│   ├── review/       # Review: entities, noise filter, publisher protocol
│   ├── memory/       # Codebase memory: outline, patterns, ProfileService
│   └── llm/          # LLM config: ModelConfig, TokenBudget
├── application/      # Use cases — orchestrates domain services
├── infrastructure/   # Concrete implementations of domain protocols
│   ├── parsing/      # Tree-sitter AST parser + code chunker
│   ├── retrieval/    # Structural, lexical (BM25), semantic (embeddings), agentic strategies
│   ├── memory/       # Outline renderer + LLM pattern analyzer
│   ├── llm_providers/# pydantic-ai Agent factory
│   ├── storage/      # Sharded codebase map + memory JSON persistence
│   └── github/       # GitHub API client + review publisher
└── interfaces/       # Entry points: review, index, bootstrap
```

## Layer Dependency Rules (CRITICAL)

```
interfaces → application → domain ← infrastructure
                             ↓
                           shared
```

- **shared**: Zero internal imports. Every layer may import from it.
- **domain**: Imports only from `shared`. Defines protocols that infrastructure satisfies.
- **application**: Imports from `domain` and `shared`. Never imports infrastructure.
- **infrastructure**: Imports from `domain` and `shared`. Implements domain protocols.
- **interfaces**: Imports from all layers. Wires everything together (composition root).

**FORBIDDEN imports:**
```
infrastructure → application
domain → infrastructure
domain → application
application → infrastructure
```

## Commands

| Command | Purpose |
|---------|---------|
| `make install` | Install all dependencies and pre-commit hooks |
| `make fmt` | Format code with ruff |
| `make lint` | Run linter |
| `make lint-fix` | Run linter with auto-fix |
| `make typecheck` | Run pyright strict mode |
| `make security` | Run security scan (bandit) |
| `make audit` | Run dependency audit (pip-audit) |
| `make check` | Run lint + typecheck + security + audit |
| `make test` | Run all tests with coverage |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make test-smoke` | Run smoke tests against live LLM providers |
| `make test-cov` | Run tests and open HTML coverage report |
| `make pre-commit` | Run all pre-commit hooks |

## Workflow

1. Write a failing test → `make test-unit` confirms failure
2. Write minimal code to pass → `make test-unit` confirms pass
3. Clean up → `make check && make test-unit` confirms no regression
4. Before any PR: `make pre-commit && make test`

## Commit Convention

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Scopes: `domain`, `infra`, `app`, `interfaces`, `shared`, `tests`, `ci`

## Style Quick Reference

- Python 3.12+ type hints: `list[str]`, `T | None` (not `Optional[T]`)
- `Protocol` over ABC for interfaces
- `@dataclass(frozen=True)` for value objects, `pydantic.BaseModel` at boundaries only
- Google-style docstrings on all public APIs
- Test naming: `test_<component>_<scenario>_<expected>`
- Line length: 88 (ruff enforced)
- See [`docs/style-guide.md`](docs/style-guide.md) for full details

## Running the Action

```yaml
- uses: sudzxd/argus@v0
  with:
    model: anthropic:claude-sonnet-4-5-20250929
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

See `action.yml` for all inputs. See `.env.example` for environment variables.
