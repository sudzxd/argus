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
    json_data: dict[str, object] | list[dict[str, object]] | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    resp.headers = headers or {}
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


# =============================================================================
# URL encoding & tree truncation
# =============================================================================


def test_get_file_content_url_encodes_special_chars(client: GitHubClient) -> None:
    response = _mock_response(text="file content")

    with _patch_httpx(response) as mock_cls:
        client.get_file_content("path with spaces/file#1.py", ref="main")

    # Verify the URL was properly encoded.
    mock_instance = mock_cls.return_value
    call_args = mock_instance.get.call_args
    url = str(call_args)
    assert "path%20with%20spaces/file%231.py" in url
    assert "path with spaces" not in url


def test_get_tree_recursive_warns_on_truncation(
    client: GitHubClient, caplog: pytest.LogCaptureFixture
) -> None:
    response = _mock_response(
        json_data={"tree": [{"path": "a.py", "type": "blob"}], "truncated": True}
    )

    import logging

    with _patch_httpx(response), caplog.at_level(logging.WARNING):
        entries, was_truncated = client.get_tree_recursive("abc123")

    assert len(entries) == 1
    assert was_truncated is True
    assert "truncated" in caplog.text


def test_get_tree_recursive_not_truncated(client: GitHubClient) -> None:
    response = _mock_response(
        json_data={"tree": [{"path": "b.py", "type": "blob"}], "truncated": False}
    )

    with _patch_httpx(response):
        entries, was_truncated = client.get_tree_recursive("abc123")

    assert len(entries) == 1
    assert was_truncated is False


# =============================================================================
# Pagination
# =============================================================================


def test_get_list_follows_pagination(client: GitHubClient) -> None:
    """_get_list should follow Link header pagination."""
    page1 = _mock_response(
        json_data=[{"id": 1}, {"id": 2}],
        headers={"link": '<https://api.github.com/next?page=2>; rel="next"'},
    )
    page2 = _mock_response(
        json_data=[{"id": 3}],
        headers={},
    )

    mock_client = MagicMock()
    mock_client.get.side_effect = [page1, page2]
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "argus.infrastructure.github.client.httpx.Client",
        return_value=mock_client,
    ):
        result = client.get_issue_comments(42)

    assert len(result) == 3
    assert result[0]["id"] == 1
    assert result[2]["id"] == 3


def test_get_list_single_page(client: GitHubClient) -> None:
    """_get_list returns single page when no Link header."""
    response = _mock_response(
        json_data=[{"id": 1}],
        headers={},
    )

    with _patch_httpx(response):
        result = client.get_issue_comments(42)

    assert len(result) == 1


def test_get_list_empty_response(client: GitHubClient) -> None:
    """_get_list handles empty list response."""
    response = _mock_response(
        json_data=[],
        headers={},
    )

    with _patch_httpx(response):
        result = client.get_issue_comments(42)

    assert result == []


# =============================================================================
# Rate limit retry (429)
# =============================================================================


def test_request_retries_on_429(client: GitHubClient) -> None:
    """GET requests retry on 429 then succeed."""
    rate_limited = _mock_response(
        status_code=429,
        text="rate limited",
        headers={"Retry-After": "0"},
    )
    ok = _mock_response(json_data={"number": 1, "title": "PR"})

    mock_client = MagicMock()
    mock_client.get.side_effect = [rate_limited, ok]
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "argus.infrastructure.github.client.httpx.Client",
        return_value=mock_client,
    ):
        result = client.get_pull_request(1)

    assert result["number"] == 1
    assert mock_client.get.call_count == 2


def test_post_retries_on_429(client: GitHubClient) -> None:
    """POST requests retry on 429 then succeed."""
    rate_limited = _mock_response(
        status_code=429,
        text="rate limited",
        headers={"Retry-After": "0"},
    )
    ok = _mock_response(status_code=201)

    mock_client = MagicMock()
    mock_client.post.side_effect = [rate_limited, ok]
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "argus.infrastructure.github.client.httpx.Client",
        return_value=mock_client,
    ):
        client.post_issue_comment(42, "comment")

    assert mock_client.post.call_count == 2


def test_request_raises_after_exhausting_retries(client: GitHubClient) -> None:
    """After max retries on 429, raises PublishError."""
    rate_limited = _mock_response(
        status_code=429,
        text="rate limited",
        headers={"Retry-After": "0"},
    )

    mock_client = MagicMock()
    mock_client.get.return_value = rate_limited
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "argus.infrastructure.github.client.httpx.Client",
            return_value=mock_client,
        ),
        pytest.raises(PublishError, match="429"),
    ):
        client.get_pull_request(1)
