"""Tests for PR context collector."""

from __future__ import annotations

from unittest.mock import MagicMock

from argus.infrastructure.github.pr_context_collector import PRContextCollector


def _make_pr_response(
    behind_by: int = 0,
    created_at: str = "2026-02-01T10:00:00Z",
) -> dict[str, object]:
    return {
        "title": "Fix auth timeout",
        "body": "Fixes #42\n\nThis PR fixes the auth timeout issue.",
        "created_at": created_at,
        "user": {"login": "sudzxd"},
        "labels": [{"name": "bug"}, {"name": "auth"}],
        "behind_by": behind_by,
        "base": {"ref": "develop"},
    }


def _make_check_runs(
    checks: list[tuple[str, str, str | None]] | None = None,
) -> list[dict[str, object]]:
    """Build check runs from (name, status, conclusion) tuples."""
    if checks is None:
        checks = [
            ("lint", "completed", "success"),
            ("test", "completed", "failure"),
        ]
    result: list[dict[str, object]] = []
    for name, status, conclusion in checks:
        run: dict[str, object] = {
            "name": name,
            "status": status,
            "conclusion": conclusion,
        }
        if conclusion == "failure":
            run["output"] = {"summary": "coverage 74% < 80%"}
        result.append(run)
    return result


# =============================================================================
# CI Status
# =============================================================================


def test_collect_ci_status_detects_failure() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = _make_check_runs()
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.ci_status.conclusion == "failure"
    assert len(ctx.ci_status.checks) == 2
    assert ctx.ci_status.checks[0].name == "lint"
    assert ctx.ci_status.checks[0].conclusion == "success"
    assert ctx.ci_status.checks[1].name == "test"
    assert ctx.ci_status.checks[1].conclusion == "failure"
    assert ctx.ci_status.checks[1].summary == "coverage 74% < 80%"


def test_collect_ci_status_all_success() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = _make_check_runs(
        [("lint", "completed", "success"), ("test", "completed", "success")]
    )
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.ci_status.conclusion == "success"


def test_collect_ci_status_pending_when_in_progress() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = _make_check_runs(
        [("lint", "completed", "success"), ("test", "in_progress", None)]
    )
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.ci_status.conclusion == "pending"


def test_collect_ci_status_pending_when_no_checks() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.ci_status.conclusion == "pending"


# =============================================================================
# PR Metadata
# =============================================================================


def test_collect_extracts_pr_metadata() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.title == "Fix auth timeout"
    assert ctx.author == "sudzxd"
    assert ctx.labels == ["bug", "auth"]
    assert "Fixes #42" in ctx.body


# =============================================================================
# Comments
# =============================================================================


def test_collect_gathers_comments() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = [
        {
            "user": {"login": "reviewer"},
            "body": "Can you add tests?",
            "created_at": "2026-02-17T10:00:00Z",
        },
    ]
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert len(ctx.comments) == 1
    assert ctx.comments[0].author == "reviewer"
    assert ctx.comments[0].body == "Can you add tests?"


# =============================================================================
# Git Health
# =============================================================================


def test_collect_computes_git_health() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response(behind_by=23)
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = []
    # Two parents = merge commit
    client.get_pr_commits.return_value = [
        {"parents": [{"sha": "a"}, {"sha": "b"}]},
    ]

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.git_health.behind_by == 23
    assert ctx.git_health.has_merge_commits is True
    assert ctx.git_health.days_open > 0


def test_collect_no_merge_commits() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = []
    client.get_pr_commits.return_value = [
        {"parents": [{"sha": "a"}]},
    ]

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.git_health.has_merge_commits is False


# =============================================================================
# Related Items
# =============================================================================


def test_collect_skips_related_by_default() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert ctx.related_items == []
    client.search_issues.assert_not_called()


def test_collect_related_items_from_body_refs() -> None:
    client = MagicMock()
    pr_data = _make_pr_response()  # body has "Fixes #42"
    client.get_pull_request.side_effect = [
        pr_data,
        # Second call fetches issue #42 details
        {
            "title": "Auth timeout",
            "state": "open",
            "body": "Timeout desc",
            "number": 42,
        },
    ]
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = []
    client.get_pr_review_comments.return_value = []
    client.get_pr_commits.return_value = []
    client.search_issues.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123", search_related=True)

    assert len(ctx.related_items) == 1
    assert ctx.related_items[0].number == 42
    assert ctx.related_items[0].title == "Auth timeout"


# =============================================================================
# Review Comments (inline code annotations)
# =============================================================================


def test_collect_merges_issue_and_review_comments() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = [
        {
            "user": {"login": "reviewer"},
            "body": "Looks good overall",
            "created_at": "2026-02-17T12:00:00Z",
        },
    ]
    client.get_pr_review_comments.return_value = [
        {
            "user": {"login": "reviewer"},
            "body": "Nit: rename this var",
            "created_at": "2026-02-17T11:00:00Z",
            "path": "src/foo.py",
            "line": 42,
        },
    ]
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert len(ctx.comments) == 2
    # Sorted by created_at — review comment first (11:00), then issue comment (12:00).
    assert ctx.comments[0].file_path == "src/foo.py"
    assert ctx.comments[0].line == 42
    assert ctx.comments[0].body == "Nit: rename this var"
    assert ctx.comments[1].file_path is None
    assert ctx.comments[1].line is None


def test_collect_filters_bot_comments() -> None:
    client = MagicMock()
    client.get_pull_request.return_value = _make_pr_response()
    client.get_check_runs.return_value = []
    client.get_issue_comments.return_value = [
        {
            "user": {"login": "github-actions[bot]"},
            "body": "Argus review posted",
            "created_at": "2026-02-17T10:00:00Z",
        },
        {
            "user": {"login": "reviewer"},
            "body": "Human comment",
            "created_at": "2026-02-17T11:00:00Z",
        },
    ]
    client.get_pr_review_comments.return_value = [
        {
            "user": {"login": "github-actions[bot]"},
            "body": "Bot inline comment",
            "created_at": "2026-02-17T10:30:00Z",
            "path": "x.py",
            "line": 1,
        },
    ]
    client.get_pr_commits.return_value = []

    collector = PRContextCollector(client=client)
    ctx = collector.collect(pr_number=1, head_sha="abc123")

    assert len(ctx.comments) == 1
    assert ctx.comments[0].author == "reviewer"
