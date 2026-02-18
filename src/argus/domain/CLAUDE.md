# Domain Layer

> Inherits all rules from root `CLAUDE.md`.

Pure domain logic. Imports only from `shared/`. Defines protocols that infrastructure implements.

## Bounded Contexts

| Context | Key files | What it does |
|---------|-----------|-------------|
| `context/` | `entities.py`, `value_objects.py`, `services.py`, `repositories.py` | `CodebaseMap` entity, `IndexingService` for full/incremental indexing, `SourceParser` + `CodebaseMapRepository` protocols |
| `retrieval/` | `strategies.py`, `services.py`, `ranker.py`, `value_objects.py` | `RetrievalStrategy` protocol, `RetrievalOrchestrator` service, `RelevanceRanker`, `ContextItem`/`RetrievalQuery` value objects |
| `review/` | `entities.py`, `services.py`, `repositories.py`, `value_objects.py` | `Review`/`ReviewComment` entities, `NoiseFilter` service, `ReviewPublisher` protocol |
| `llm/` | `value_objects.py` | `ModelConfig` (model string, max_tokens, temperature), `TokenBudget` (retrieval/generation split) |
| `memory/` | `value_objects.py`, `repositories.py`, `services.py` | `CodebaseMemory`, `CodebaseOutline`, `PatternEntry` value objects; `CodebaseMemoryRepository` + `PatternAnalyzer` protocols; `ProfileService` for pattern analysis orchestration |

## Rules

- Never import from `infrastructure`, `application`, or `interfaces`.
- Define interfaces as `Protocol` classes, not ABCs.
- All value objects use `@dataclass(frozen=True)`.
- Domain services are pure functions/classes with no I/O.
