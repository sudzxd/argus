# Application Layer

> Inherits all rules from root `CLAUDE.md`.

Use cases that orchestrate domain services. Imports from `domain/` and `shared/` only.

## Modules

| File | What it does |
|------|-------------|
| `dto.py` | `IndexCodebaseCommand`/`Result`, `ReviewPullRequestCommand`/`Result` — command/result objects |
| `index_codebase.py` | Indexes source files into a `CodebaseMap` (full or incremental) |
| `review_pull_request.py` | Full pipeline: index → retrieve context → generate review → filter noise → publish |

## Rules

- **Never import from `infrastructure` or `interfaces`.** Depend on domain protocols only.
- **Mock ALL infrastructure in tests.** Inject fakes for `SourceParser`, `CodebaseMapRepository`, `RetrievalStrategy`, `ReviewPublisher`, etc.
- Use cases receive dependencies via constructor injection.
