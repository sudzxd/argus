"""GitHub REST API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import httpx

from argus.infrastructure.constants import GitHubAPI
from argus.shared.constants import DEFAULT_TIMEOUT_SECONDS
from argus.shared.exceptions import PublishError
from argus.shared.types import FilePath

# =============================================================================
# CLIENT
# =============================================================================

_STATUS_OK_MAX = 299


@dataclass
class GitHubClient:
    """Thin wrapper around the GitHub REST API."""

    token: str
    repo: str

    def get_pull_request(self, pr_number: int) -> dict[str, object]:
        """Fetch PR metadata.

        Raises:
            PublishError: If the API call fails.
        """
        return self._get(f"/repos/{self.repo}/pulls/{pr_number}")

    def get_pull_request_diff(self, pr_number: int) -> str:
        """Fetch the unified diff for a PR.

        Raises:
            PublishError: If the API call fails.
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{self.repo}/pulls/{pr_number}"
        headers = self._headers()
        headers["accept"] = GitHubAPI.ACCEPT_DIFF
        response = self._request(url, headers)
        return response.text

    def get_file_content(self, path: FilePath, ref: str) -> str:
        """Fetch raw file content at a specific ref.

        Raises:
            PublishError: If the API call fails.
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{self.repo}/contents/{path}?ref={ref}"
        headers = self._headers()
        headers["accept"] = "application/vnd.github.v3.raw"
        response = self._request(url, headers)
        return response.text

    def post_issue_comment(self, pr_number: int, body: str) -> None:
        """Post a comment on a PR (as issue comment).

        Raises:
            PublishError: If the API call fails.
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{self.repo}/issues/{pr_number}/comments"
        self._post(url, {"body": body})

    def post_review(
        self,
        pr_number: int,
        body: str,
        comments: list[dict[str, object]],
    ) -> None:
        """Submit a PR review with inline comments.

        Raises:
            PublishError: If the API call fails.
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{self.repo}/pulls/{pr_number}/reviews"
        payload: dict[str, object] = {
            "body": body,
            "event": "COMMENT",
            "comments": comments,
        }
        self._post(url, payload)

    def get_repo_default_branch_sha(self) -> str:
        """Fetch the SHA of the default branch's HEAD.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._get(f"/repos/{self.repo}")
        default_branch = str(data.get("default_branch", "main"))
        branch_data = self._get(f"/repos/{self.repo}/branches/{default_branch}")
        commit_obj: object = branch_data.get("commit")
        if isinstance(commit_obj, dict):
            commit_data = cast(dict[str, object], commit_obj)
            sha_val = commit_data.get("sha")
            if isinstance(sha_val, str):
                return sha_val
        msg = "Cannot extract default branch SHA"
        raise PublishError(msg)

    def get_tree_recursive(self, sha: str) -> list[dict[str, object]]:
        """Fetch the full file tree for a commit SHA (recursive).

        Returns:
            List of tree entries with 'path', 'type', 'size' fields.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._get(f"/repos/{self.repo}/git/trees/{sha}?recursive=1")
        tree = data.get("tree")
        if isinstance(tree, list):
            return tree  # type: ignore[return-value]
        return []

    def _get(self, path: str) -> dict[str, object]:
        url = f"{GitHubAPI.BASE_URL}{path}"
        response = self._request(url, self._headers())
        return response.json()  # type: ignore[no-any-return]

    def _post(self, url: str, payload: dict[str, object]) -> None:
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            raise PublishError(f"GitHub API error: {e}") from e

        if response.status_code > _STATUS_OK_MAX:
            raise PublishError(
                f"GitHub API HTTP {response.status_code}: {response.text}"
            )

    def _request(self, url: str, headers: dict[str, str]) -> httpx.Response:
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.get(url, headers=headers)
        except httpx.HTTPError as e:
            raise PublishError(f"GitHub API error: {e}") from e

        if response.status_code > _STATUS_OK_MAX:
            raise PublishError(
                f"GitHub API HTTP {response.status_code}: {response.text}"
            )
        return response

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.token}",
            "accept": GitHubAPI.ACCEPT_JSON,
        }
