"""GitHub REST API client."""

from __future__ import annotations

import logging
import re
import urllib.parse

from dataclasses import dataclass
from typing import cast

import httpx

from argus.infrastructure.constants import GitHubAPI
from argus.shared.constants import DEFAULT_TIMEOUT_SECONDS
from argus.shared.exceptions import PublishError
from argus.shared.types import FilePath

logger = logging.getLogger(__name__)

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def _next_page_url(response: httpx.Response) -> str | None:
    """Extract the next page URL from a GitHub ``Link`` header."""
    link = response.headers.get("link", "")
    match = _LINK_NEXT_RE.search(link)
    return match.group(1) if match else None


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
        encoded_path = urllib.parse.quote(str(path), safe="/")
        base = f"{GitHubAPI.BASE_URL}/repos/{self.repo}/contents"
        url = f"{base}/{encoded_path}?ref={ref}"
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
        if data.get("truncated"):
            logger.warning(
                "GitHub tree response was truncated for SHA %s; "
                "some files may be missing from the codebase map",
                sha,
            )
        tree = data.get("tree")
        if isinstance(tree, list):
            return tree  # type: ignore[return-value]
        return []

    def compare_commits(self, base: str, head: str) -> list[str]:
        """Get the list of changed file paths between two commits.

        Args:
            base: Base commit SHA or branch name.
            head: Head commit SHA or branch name.

        Returns:
            List of file paths that were added, modified, or removed.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._get(f"/repos/{self.repo}/compare/{base}...{head}")
        files = data.get("files")
        if not isinstance(files, list):
            return []
        file_list = cast(list[dict[str, object]], files)
        paths: list[str] = []
        for file_entry in file_list:
            filename: object = file_entry.get("filename")
            if isinstance(filename, str):
                paths.append(filename)
        return paths

    # =================================================================
    # PR metadata helpers
    # =================================================================

    def get_check_runs(self, commit_sha: str) -> list[dict[str, object]]:
        """Fetch check runs for a commit.

        Returns:
            List of check-run dicts.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._get(f"/repos/{self.repo}/commits/{commit_sha}/check-runs")
        runs = data.get("check_runs")
        if isinstance(runs, list):
            return runs  # type: ignore[return-value]
        return []

    def get_issue_comments(self, pr_number: int) -> list[dict[str, object]]:
        """Fetch issue comments on a PR.

        Returns:
            List of comment dicts.

        Raises:
            PublishError: If the API call fails.
        """
        return self._get_list(f"/repos/{self.repo}/issues/{pr_number}/comments")

    def get_pr_review_comments(self, pr_number: int) -> list[dict[str, object]]:
        """Fetch review comments (inline code annotations) on a PR.

        Returns:
            List of review comment dicts.

        Raises:
            PublishError: If the API call fails.
        """
        return self._get_list(f"/repos/{self.repo}/pulls/{pr_number}/comments")

    def get_pr_commits(self, pr_number: int) -> list[dict[str, object]]:
        """Fetch commits on a PR.

        Returns:
            List of commit dicts.

        Raises:
            PublishError: If the API call fails.
        """
        return self._get_list(f"/repos/{self.repo}/pulls/{pr_number}/commits")

    def search_issues(self, query: str) -> list[dict[str, object]]:
        """Search issues and PRs by query.

        Returns:
            List of issue/PR dicts from search results.

        Raises:
            PublishError: If the API call fails.
        """
        encoded = urllib.parse.quote(f"{query} repo:{self.repo}")
        data = self._get(f"/search/issues?q={encoded}")
        items = data.get("items")
        if isinstance(items, list):
            return items  # type: ignore[return-value]
        return []

    # =================================================================
    # Git Data API — low-level tree / blob / commit manipulation
    # =================================================================

    def get_ref_sha(self, branch: str) -> str | None:
        """Get the commit SHA that a branch ref points to.

        Returns:
            The commit SHA, or None if the branch does not exist.
        """
        url = f"{GitHubAPI.BASE_URL}/repos/{self.repo}/git/ref/heads/{branch}"
        try:
            response = self._request(url, self._headers())
        except PublishError:
            return None
        data: dict[str, object] = response.json()
        obj = data.get("object")
        if isinstance(obj, dict):
            obj_data = cast(dict[str, object], obj)
            sha: object = obj_data.get("sha")
            if isinstance(sha, str):
                return sha
        return None

    def get_commit_tree_sha(self, commit_sha: str) -> str:
        """Get the tree SHA for a commit.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._get(f"/repos/{self.repo}/git/commits/{commit_sha}")
        tree = data.get("tree")
        if isinstance(tree, dict):
            tree_data = cast(dict[str, object], tree)
            sha: object = tree_data.get("sha")
            if isinstance(sha, str):
                return sha
        msg = f"Cannot extract tree SHA from commit {commit_sha}"
        raise PublishError(msg)

    def get_tree_entries_flat(self, tree_sha: str) -> list[dict[str, object]]:
        """Get entries for a tree (non-recursive).

        Returns:
            List of tree entry dicts with 'path', 'sha', 'type', etc.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._get(f"/repos/{self.repo}/git/trees/{tree_sha}")
        tree = data.get("tree")
        if isinstance(tree, list):
            return tree  # type: ignore[return-value]
        return []

    def get_blob_content(self, blob_sha: str) -> bytes:
        """Download a blob's content (base64-decoded).

        Raises:
            PublishError: If the API call fails.
        """
        import base64

        data = self._get(f"/repos/{self.repo}/git/blobs/{blob_sha}")
        content = data.get("content")
        if isinstance(content, str):
            return base64.b64decode(content)
        msg = f"Cannot extract content from blob {blob_sha}"
        raise PublishError(msg)

    def create_blob(self, content_b64: str) -> str:
        """Create a blob from base64-encoded content.

        Returns:
            The SHA of the created blob.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._post_json(
            f"/repos/{self.repo}/git/blobs",
            {"content": content_b64, "encoding": "base64"},
        )
        sha = data.get("sha")
        if isinstance(sha, str):
            return sha
        msg = "Cannot extract SHA from created blob"
        raise PublishError(msg)

    def create_tree(
        self,
        entries: list[dict[str, str]],
        base_tree: str | None = None,
    ) -> str:
        """Create a tree object.

        Args:
            entries: List of tree entry dicts with path, mode, type, sha.
            base_tree: Optional base tree SHA for incremental updates.

        Returns:
            The SHA of the created tree.

        Raises:
            PublishError: If the API call fails.
        """
        payload: dict[str, object] = {"tree": entries}
        if base_tree is not None:
            payload["base_tree"] = base_tree
        data = self._post_json(f"/repos/{self.repo}/git/trees", payload)
        sha = data.get("sha")
        if isinstance(sha, str):
            return sha
        msg = "Cannot extract SHA from created tree"
        raise PublishError(msg)

    def create_commit(
        self,
        message: str,
        tree_sha: str,
        parents: list[str],
    ) -> str:
        """Create a commit object.

        Returns:
            The SHA of the created commit.

        Raises:
            PublishError: If the API call fails.
        """
        data = self._post_json(
            f"/repos/{self.repo}/git/commits",
            {"message": message, "tree": tree_sha, "parents": parents},
        )
        sha = data.get("sha")
        if isinstance(sha, str):
            return sha
        msg = "Cannot extract SHA from created commit"
        raise PublishError(msg)

    def create_ref(self, ref: str, sha: str) -> None:
        """Create a new Git ref (e.g. refs/heads/branch-name).

        Raises:
            PublishError: If the API call fails.
        """
        self._post_json(
            f"/repos/{self.repo}/git/refs",
            {"ref": ref, "sha": sha},
        )

    def update_ref(self, ref: str, sha: str) -> None:
        """Update an existing Git ref.

        Raises:
            PublishError: If the API call fails.
        """
        self._patch(
            f"/repos/{self.repo}/git/refs/{ref}",
            {"sha": sha, "force": True},
        )

    # =================================================================
    # HTTP helpers
    # =================================================================

    def _get(self, path: str) -> dict[str, object]:
        url = f"{GitHubAPI.BASE_URL}{path}"
        response = self._request(url, self._headers())
        return response.json()  # type: ignore[no-any-return]

    def _get_list(self, path: str) -> list[dict[str, object]]:
        url: str | None = f"{GitHubAPI.BASE_URL}{path}"
        all_items: list[dict[str, object]] = []
        while url is not None:
            response = self._request(url, self._headers())
            data = response.json()
            if isinstance(data, list):
                all_items.extend(cast(list[dict[str, object]], data))
            url = _next_page_url(response)
        return all_items

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

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        """POST and return the response JSON body."""
        url = f"{GitHubAPI.BASE_URL}{path}"
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            raise PublishError(f"GitHub API error: {e}") from e

        if response.status_code > _STATUS_OK_MAX:
            raise PublishError(
                f"GitHub API HTTP {response.status_code}: {response.text}"
            )
        return response.json()  # type: ignore[no-any-return]

    def _patch(self, path: str, payload: dict[str, object]) -> None:
        """PATCH request."""
        url = f"{GitHubAPI.BASE_URL}{path}"
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.patch(url, json=payload, headers=self._headers())
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
