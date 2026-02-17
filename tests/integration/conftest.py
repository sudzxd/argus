"""Shared fixtures for integration tests."""

from __future__ import annotations

import json
import textwrap

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from argus.interfaces.review_generator import ReviewOutput


@pytest.fixture
def github_event(tmp_path: Path) -> Path:
    """Create a GitHub event JSON file for a pull request."""
    event = {
        "pull_request": {
            "number": 42,
            "head": {"sha": "abc123def456"},
        },
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    return event_path


@pytest.fixture
def sample_diff() -> str:
    return textwrap.dedent("""\
        diff --git a/src/auth.py b/src/auth.py
        index 1234567..abcdefg 100644
        --- a/src/auth.py
        +++ b/src/auth.py
        @@ -1,3 +1,5 @@
        +import hashlib
        +
         def login(user, password):
             return check_password(user, password)
    """)


@pytest.fixture
def sample_file_content() -> str:
    return textwrap.dedent("""\
        import hashlib

        def login(user, password):
            return check_password(user, password)
    """)


@pytest.fixture
def sample_review_output() -> ReviewOutput:
    """A review output matching the sample diff."""
    return ReviewOutput(
        summary_description="Added hashlib import for password hashing.",
        summary_risks=["Unused import if not used downstream"],
        summary_strengths=["Moving toward secure password handling"],
        summary_verdict="Approve with minor suggestions",
        comments=[
            ReviewOutput.CommentOutput(
                file="src/auth.py",
                line_start=1,
                line_end=1,
                severity="suggestion",
                category="style",
                body="Consider using 'from hashlib import sha256' for clarity.",
                confidence=0.85,
                suggestion="from hashlib import sha256",
            ),
            ReviewOutput.CommentOutput(
                file="src/auth.py",
                line_start=4,
                line_end=4,
                severity="warning",
                category="security",
                body="check_password should use constant-time comparison.",
                confidence=0.92,
                suggestion=None,
            ),
        ],
    )


@pytest.fixture
def low_confidence_review_output() -> ReviewOutput:
    """A review output with a low-confidence comment for filtering tests."""
    return ReviewOutput(
        summary_description="Minor changes.",
        summary_risks=[],
        summary_strengths=["Clean code"],
        summary_verdict="Approve",
        comments=[
            ReviewOutput.CommentOutput(
                file="src/auth.py",
                line_start=1,
                line_end=1,
                severity="suggestion",
                category="style",
                body="High confidence suggestion.",
                confidence=0.95,
                suggestion=None,
            ),
            ReviewOutput.CommentOutput(
                file="src/auth.py",
                line_start=2,
                line_end=2,
                severity="suggestion",
                category="style",
                body="Low confidence — should be filtered.",
                confidence=0.3,
                suggestion=None,
            ),
        ],
    )


@pytest.fixture
def ignored_path_review_output() -> ReviewOutput:
    """Review output with comments on ignored and non-ignored paths."""
    return ReviewOutput(
        summary_description="Changes across vendor and src.",
        summary_risks=[],
        summary_strengths=[],
        summary_verdict="Approve",
        comments=[
            ReviewOutput.CommentOutput(
                file="src/auth.py",
                line_start=1,
                line_end=1,
                severity="warning",
                category="bug",
                body="Real issue in src.",
                confidence=0.9,
                suggestion=None,
            ),
            ReviewOutput.CommentOutput(
                file="vendor/lib.py",
                line_start=1,
                line_end=1,
                severity="warning",
                category="bug",
                body="Issue in vendor — should be ignored.",
                confidence=0.9,
                suggestion=None,
            ),
        ],
    )


@pytest.fixture
def mock_llm_agent(sample_review_output: ReviewOutput) -> MagicMock:
    """Mock pydantic-ai agent that returns the sample review output."""
    agent = MagicMock()
    result = MagicMock()
    result.output = sample_review_output
    agent.run_sync.return_value = result
    return agent
