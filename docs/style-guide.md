# Style Guide

Python conventions for Argus contributors.

## Type Hints

Use modern Python 3.12+ syntax:

```python
# Good
def process(items: list[str]) -> dict[str, int]: ...
name: str | None = None

# Avoid
from typing import Dict, List, Optional
def process(items: List[str]) -> Dict[str, int]: ...
name: Optional[str] = None
```

- `list[str]` not `List[str]`
- `dict[K, V]` not `Dict[K, V]`
- `T | None` not `Optional[T]`
- `str | int` not `Union[str, int]`

Use `typing` only for: `Any`, `TypeVar`, `Generic`, `Protocol`, `Callable`, `TypeAlias`

## Docstrings

Google-style. All public functions, classes, and modules.

```python
def rank(items: list[ContextItem], budget: TokenBudget) -> RetrievalResult:
    """Rank and budget context items for the review prompt.

    Args:
        items: Unranked context items from all retrieval strategies.
        budget: Maximum token allocation for the retrieval result.

    Returns:
        Deduplicated, scored, and budget-constrained retrieval result.

    Raises:
        BudgetExceededError: If no valid subset fits within the budget.
    """
```

- Don't repeat type information already in the signature.
- Document exceptions that callers should handle.
- Skip docstrings on private helpers unless the logic is non-obvious.

## Module Layout

```python
"""Module docstring describing domain responsibility."""

from __future__ import annotations

# =============================================================================
# IMPORTS
# =============================================================================

# Standard library
import json
from pathlib import Path

# Third-party
from pydantic import BaseModel

# Project
from argus.shared.types import FilePath
from argus.shared.exceptions import IndexingError

# =============================================================================
# TYPES & CONSTANTS
# =============================================================================

DEFAULT_TOKEN_BUDGET = 128_000

# =============================================================================
# PUBLIC API
# =============================================================================

def public_function() -> None:
    """Public function."""
    ...

# =============================================================================
# CORE CLASSES
# =============================================================================

class MyService:
    """Main class."""
    ...

# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _private_helper() -> None:
    """Private helper."""
    ...
```

Import order within sections is enforced by ruff.

## Data Modeling

Use `dataclass` for domain value objects and entities. Use `pydantic.BaseModel` at boundaries (serialization, LLM structured output, configuration).

```python
# Domain — dataclass
from dataclasses import dataclass

@dataclass(frozen=True)
class FileEntry:
    path: FilePath
    symbols: list[Symbol]
    imports: list[FilePath]
    summary: str | None = None

# Boundary — pydantic
from pydantic import BaseModel

class ReviewCommentSchema(BaseModel):
    file: str
    line_start: int
    line_end: int
    severity: str
    body: str
```

- `frozen=True` on value objects — immutability by default.
- Pydantic at infrastructure boundaries only. Domain stays framework-free.

## Protocols Over ABCs

Define interfaces with `Protocol`, not `ABC`. No forced inheritance.

```python
from typing import Protocol

class RetrievalStrategy(Protocol):
    def retrieve(self, query: RetrievalQuery) -> list[ContextItem]: ...

class LLMProvider(Protocol):
    def complete(self, messages: list[Message]) -> Completion: ...
```

Implementations don't need to inherit — they just need to match the shape. Duck typing, statically verified by pyright.

## Error Handling

Typed exception hierarchy. Fail fast with context.

```python
# Define
class IndexingError(ArgusError):
    def __init__(self, path: FilePath, reason: str) -> None:
        self.path = path
        super().__init__(f"Failed to index {path}: {reason}")

# Raise
raise IndexingError(path, "unsupported language")

# Catch at use-case boundary
try:
    context = indexing_service.index(files)
except IndexingError as e:
    logger.warning("Skipping file", path=e.path)
```

- Never catch bare `Exception` in domain or application code.
- Let unexpected errors propagate — the entry point handles them.
- Exceptions carry structured context (the file, the stage, what was attempted).

## Testing

### Naming

```
test_<component>_<scenario>_<expected>
```

```python
def test_ranker_with_duplicate_items_deduplicates():
    ...

def test_structural_strategy_returns_direct_dependents():
    ...
```

### Structure

```python
def test_incremental_update_only_reparses_changed_files():
    # Arrange
    codebase_map = build_map_with(files=["a.py", "b.py", "c.py"])
    changed = ["b.py"]

    # Act
    updated = indexing_service.incremental_update(codebase_map, changed)

    # Assert
    assert updated.get("a.py").last_indexed == codebase_map.get("a.py").last_indexed
    assert updated.get("b.py").last_indexed != codebase_map.get("b.py").last_indexed
```

### Coverage

- Domain: 95%+
- Application: 90%+
- Infrastructure: 80%+
- New code: must not decrease overall coverage.

## Formatting

- Line length: 88 characters
- 4 spaces indentation
- Enforced by ruff — don't fight the formatter.

## Naming

- `snake_case` for functions, methods, variables, modules
- `PascalCase` for classes, protocols, type aliases
- `UPPER_SNAKE_CASE` for module-level constants
- Private members prefixed with `_`
- No abbreviations unless universally understood (`url`, `ast`, `llm`)
