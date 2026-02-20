"""PR context collector — gathers metadata, CI status, comments, git health."""

from __future__ import annotations

import logging
import re

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from argus.domain.review.value_objects import (
    CheckRun,
    CIStatus,
    GitHealth,
    PRComment,
    PRContext,
    RelatedItem,
)
from argus.infrastructure.github.client import GitHubClient

logger = logging.getLogger(__name__)

_MAX_SUMMARY_CHARS = 200
_MAX_RELATED_ITEMS = 5
_MAX_BODY_CHARS = 200
_ISSUE_REF_RE = re.compile(
    r"(?:fixes|closes|resolves|fix|close|resolve)\s+#(\d+)",
    re.IGNORECASE,
)


@dataclass
class PRContextCollector:
    """Collects PR metadata, CI status, comments, git health, related issues."""

    client: GitHubClient

    def collect(
        self,
        pr_number: int,
        head_sha: str,
        search_related: bool = False,
    ) -> PRContext:
        """Collect full PR context for review enrichment.

        Args:
            pr_number: Pull request number.
            head_sha: HEAD commit SHA for CI check lookup.
            search_related: Whether to search for related issues/PRs.

        Returns:
            PRContext with metadata, CI status, comments, and git health.
        """
        pr_data = self.client.get_pull_request(pr_number)

        title = str(pr_data.get("title", ""))
        body = str(pr_data.get("body", "") or "")
        created_at = str(pr_data.get("created_at", ""))
        labels = self._extract_labels(pr_data)
        author = self._extract_author(pr_data)
        behind_by = self._extract_behind_by(pr_data)

        ci_status = self._collect_ci_status(head_sha)
        comments = self._collect_comments(pr_number)
        git_health = self._compute_git_health(pr_number, behind_by, created_at)

        related_items: list[RelatedItem] = []
        if search_related:
            related_items = self._collect_related_items(title, body)

        return PRContext(
            title=title,
            body=body,
            author=author,
            created_at=created_at,
            labels=labels,
            comments=comments,
            ci_status=ci_status,
            git_health=git_health,
            related_items=related_items,
        )

    def _extract_labels(self, pr_data: dict[str, object]) -> list[str]:
        raw_labels = pr_data.get("labels")
        if not isinstance(raw_labels, list):
            return []
        label_list = cast(list[dict[str, object]], raw_labels)
        labels: list[str] = []
        for label_data in label_list:
            name = label_data.get("name")
            if isinstance(name, str):
                labels.append(name)
        return labels

    def _extract_author(self, pr_data: dict[str, object]) -> str:
        user = pr_data.get("user")
        if isinstance(user, dict):
            user_data = cast(dict[str, object], user)
            login = user_data.get("login")
            if isinstance(login, str):
                return login
        return "unknown"

    def _extract_behind_by(self, pr_data: dict[str, object]) -> int:
        base = pr_data.get("base")
        if not isinstance(base, dict):
            return 0
        # behind_by is at the top level of the PR response, not in base
        behind = pr_data.get("behind_by")
        if isinstance(behind, int):
            return behind
        return 0

    def _collect_ci_status(self, head_sha: str) -> CIStatus:
        raw_checks = self.client.get_check_runs(head_sha)
        checks: list[CheckRun] = []
        has_failure = False
        all_complete = True

        for check_data in raw_checks:
            name = str(check_data.get("name", ""))
            status = str(check_data.get("status", ""))
            conclusion_raw = check_data.get("conclusion")
            conclusion = str(conclusion_raw) if conclusion_raw is not None else None

            summary: str | None = None
            if conclusion == "failure":
                has_failure = True
                output = check_data.get("output")
                if isinstance(output, dict):
                    output_data = cast(dict[str, object], output)
                    raw_summary = output_data.get("summary")
                    if isinstance(raw_summary, str):
                        summary = raw_summary[:_MAX_SUMMARY_CHARS]

            if status != "completed":
                all_complete = False

            checks.append(
                CheckRun(
                    name=name,
                    status=status,
                    conclusion=conclusion,
                    summary=summary,
                )
            )

        if not checks:
            overall = "pending"
        elif has_failure:
            overall = "failure"
        elif all_complete:
            overall = "success"
        else:
            overall = "pending"

        return CIStatus(conclusion=overall, checks=checks)

    def _collect_comments(self, pr_number: int) -> list[PRComment]:
        raw_comments = self.client.get_issue_comments(pr_number)
        comments: list[PRComment] = []
        for comment_data in raw_comments:
            user = comment_data.get("user")
            author = "unknown"
            if isinstance(user, dict):
                user_data = cast(dict[str, object], user)
                login = user_data.get("login")
                if isinstance(login, str):
                    author = login
            body = str(comment_data.get("body", ""))
            created_at = str(comment_data.get("created_at", ""))
            comments.append(PRComment(author=author, body=body, created_at=created_at))
        return comments

    def _compute_git_health(
        self,
        pr_number: int,
        behind_by: int,
        created_at: str,
    ) -> GitHealth:
        # Compute days open.
        days_open = 0
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                now = datetime.now(UTC)
                days_open = (now - created).days
            except ValueError:
                pass

        # Check for merge commits.
        has_merge_commits = False
        try:
            commits = self.client.get_pr_commits(pr_number)
            for commit_data in commits:
                parents = commit_data.get("parents")
                if isinstance(parents, list) and len(parents) > 1:  # type: ignore[arg-type]
                    has_merge_commits = True
                    break
        except Exception:
            logger.debug("Could not fetch PR commits for merge commit check")

        return GitHealth(
            behind_by=behind_by,
            has_merge_commits=has_merge_commits,
            days_open=days_open,
        )

    def _collect_related_items(
        self,
        title: str,
        body: str,
    ) -> list[RelatedItem]:
        items: list[RelatedItem] = []
        seen_numbers: set[int] = set()

        # Extract linked issue refs from body.
        for match in _ISSUE_REF_RE.finditer(body):
            number = int(match.group(1))
            if number not in seen_numbers:
                seen_numbers.add(number)

        # Search by title keywords.
        try:
            search_results = self.client.search_issues(title)
            for item_data in search_results[:_MAX_RELATED_ITEMS]:
                number = item_data.get("number")
                if not isinstance(number, int) or number in seen_numbers:
                    continue
                seen_numbers.add(number)
        except Exception:
            logger.debug("Issue search failed, continuing with linked refs only")

        # Fetch details for all discovered numbers.
        for number in list(seen_numbers)[:_MAX_RELATED_ITEMS]:
            try:
                issue_data = self.client.get_pull_request(number)
                item_title = str(issue_data.get("title", ""))
                state = str(issue_data.get("state", ""))
                item_body = issue_data.get("body")
                body_str = str(item_body)[:_MAX_BODY_CHARS] if item_body else None
                kind = (
                    "pull_request"
                    if issue_data.get("pull_request") is not None
                    else "issue"
                )
                items.append(
                    RelatedItem(
                        kind=kind,
                        number=number,
                        title=item_title,
                        state=state,
                        body=body_str,
                    )
                )
            except Exception:
                logger.debug("Could not fetch details for #%d", number)

        return items
