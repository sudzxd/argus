"""Tests for GitHub REST API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argus.infrastructure.github.client import GitHubClient
from argus.shared.exceptions import PublishError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(token="test-token", repo="org/repo")


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, object] | None = None,
    text: str = "",
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def _patch_httpx(response: MagicMock):
    mock_client = MagicMock()
    mock_client.get.return_value = response
    mock_client.post.return_value = response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    return patch(
        "argus.infrastructure.github.client.httpx.Client",
        return_value=mock_client,
    )


# =============================================================================
# GET operations
# =============================================================================


def test_get_pull_request_returns_data(client: GitHubClient) -> None:
    response = _mock_response(json_data={"number": 42, "title": "Fix bug"})

    with _patch_httpx(response):
        result = client.get_pull_request(42)

    assert result["number"] == 42
    assert result["title"] == "Fix bug"


def test_get_pull_request_diff_returns_text(client: GitHubClient) -> None:
    response = _mock_response(text="diff --git a/file.py b/file.py\n")

    with _patch_httpx(response):
        result = client.get_pull_request_diff(42)

    assert "diff --git" in result


def test_get_raises_publish_error_on_failure(client: GitHubClient) -> None:
    response = _mock_response(status_code=404, text="Not Found")

    with _patch_httpx(response), pytest.raises(PublishError):
        client.get_pull_request(999)


# =============================================================================
# POST operations
# =============================================================================


def test_post_issue_comment_succeeds(client: GitHubClient) -> None:
    response = _mock_response(status_code=201)

    with _patch_httpx(response):
        client.post_issue_comment(42, "Great PR!")  # should not raise


def test_post_review_succeeds(client: GitHubClient) -> None:
    response = _mock_response(status_code=200)

    with _patch_httpx(response):
        client.post_review(
            pr_number=42,
            body="Review summary",
            comments=[{"path": "a.py", "body": "Fix this", "line": 10}],
        )  # should not raise


def test_post_raises_publish_error_on_failure(client: GitHubClient) -> None:
    response = _mock_response(status_code=422, text="Validation failed")

    with _patch_httpx(response), pytest.raises(PublishError):
        client.post_issue_comment(42, "comment")
