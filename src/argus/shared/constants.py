"""Centralized defaults for Argus. Overridable via configuration."""

from __future__ import annotations

# =============================================================================
# TOKEN BUDGETS
# =============================================================================

DEFAULT_TOKEN_BUDGET = 128_000
DEFAULT_RETRIEVAL_BUDGET_RATIO = 0.6
DEFAULT_GENERATION_BUDGET_RATIO = 0.4

# =============================================================================
# RETRIEVAL BUDGET SPLITS (fraction of retrieval budget per tier)
# =============================================================================

STRUCTURAL_BUDGET_RATIO = 0.4
LEXICAL_BUDGET_RATIO = 0.3
SEMANTIC_BUDGET_RATIO = 0.2  # Reserved for future embedding-based retrieval
AGENTIC_BUDGET_RATIO = 0.1

# =============================================================================
# INDEXING LIMITS
# =============================================================================

MAX_FILES_PER_INDEX_RUN = 5_000
MAX_FILE_SIZE_BYTES = 1_000_000
MAX_AGENTIC_ITERATIONS = 5

# =============================================================================
# REVIEW
# =============================================================================

DEFAULT_CONFIDENCE_THRESHOLD = 0.7
MAX_INLINE_COMMENTS = 50

# =============================================================================
# SUPPORTED LANGUAGES (tree-sitter grammar names)
# =============================================================================

SUPPORTED_LANGUAGES = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
        "c",
        "cpp",
        "ruby",
        "kotlin",
        "swift",
    }
)

# =============================================================================
# CODEBASE MEMORY
# =============================================================================

DEFAULT_OUTLINE_TOKEN_BUDGET = 4_000
MAX_PATTERN_ENTRIES = 30
MIN_PATTERN_CONFIDENCE = 0.3

# =============================================================================
# RETRY / TIMEOUTS
# =============================================================================

DEFAULT_RETRY_LIMIT = 3
DEFAULT_TIMEOUT_SECONDS = 120
