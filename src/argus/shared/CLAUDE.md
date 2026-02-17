# Shared Kernel

> Inherits all rules from root `CLAUDE.md`.

The foundation layer imported by every other layer. Has zero internal imports.

## Modules

| File | What's in it |
|------|-------------|
| `types.py` | `FilePath`, `CommitSHA`, `TokenCount`, `LineRange`, `Severity`, `Category` |
| `exceptions.py` | `ArgusError` hierarchy — 11 typed exception classes |
| `constants.py` | Token budgets, retrieval splits, indexing limits, review defaults, supported languages |

## Rules

- Changes here affect every layer. Keep backwards-compatible.
- Add a new type/exception only when needed across multiple bounded contexts.
- Never add imports from other `argus` packages.
