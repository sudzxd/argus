"""GitHub PR review publisher."""

from __future__ import annotations

import logging
import re

from dataclasses import dataclass

from argus.domain.review.entities import Review, ReviewComment
from argus.infrastructure.constants import SeverityLabel
from argus.infrastructure.github.client import GitHubClient
from argus.shared.exceptions import PublishError
from argus.shared.types import Severity

logger = logging.getLogger(__name__)

# =============================================================================
# SEVERITY LABEL MAPPING
# =============================================================================

_SEVERITY_TO_LABEL: dict[Severity, SeverityLabel] = {
    Severity.CRITICAL: SeverityLabel.CRITICAL,
    Severity.WARNING: SeverityLabel.WARNING,
    Severity.SUGGESTION: SeverityLabel.SUGGESTION,
    Severity.PRAISE: SeverityLabel.PRAISE,
}

# =============================================================================
# PUBLISHER
# =============================================================================


@dataclass
class GitHubReviewPublisher:
    """Implements ReviewPublisher by posting to the GitHub PR API."""

    client: GitHubClient
    diff: str = ""

    def publish(self, review: Review, pr_number: int) -> None:
        """Post a review to a pull request.

        Posts the summary as the review body and each comment as an
        inline review comment at the appropriate file and line.
        Comments whose lines cannot be mapped to a diff position are
        appended to the body text.
        """
        positions = _parse_diff_positions(self.diff) if self.diff else {}

        inline_comments: list[dict[str, object]] = []
        body_comments: list[ReviewComment] = []

        for comment in review.comments:
            formatted = self._try_format_comment(comment, positions)
            if formatted is not None:
                inline_comments.append(formatted)
            else:
                body_comments.append(comment)

        summary_text = self._format_summary(review)

        if body_comments:
            summary_text += "\n\n### Additional Comments\n"
            for c in body_comments:
                label = _SEVERITY_TO_LABEL.get(c.severity, SeverityLabel.SUGGESTION)
                summary_text += (
                    f"\n**{c.file}:{c.line_range.start}** {label} {c.body}\n"
                )
                if c.suggestion:
                    summary_text += f"```suggestion\n{c.suggestion}\n```\n"

        if inline_comments:
            try:
                self.client.post_review(
                    pr_number=pr_number,
                    body=summary_text,
                    comments=inline_comments,
                )
            except PublishError as exc:
                logger.warning("Batch review failed: %s", exc)
                self._post_comments_individually(
                    pr_number,
                    summary_text,
                    inline_comments,
                )
        else:
            self.client.post_issue_comment(
                pr_number=pr_number,
                body=summary_text,
            )

    def _post_comments_individually(
        self,
        pr_number: int,
        summary_text: str,
        inline_comments: list[dict[str, object]],
    ) -> None:
        """Try posting each inline comment as a single review, skip failures."""
        self.client.post_issue_comment(pr_number=pr_number, body=summary_text)

        failed: list[dict[str, object]] = []
        for comment in inline_comments:
            try:
                self.client.post_review(
                    pr_number=pr_number,
                    body="",
                    comments=[comment],
                )
            except PublishError:
                logger.debug(
                    "Skipping comment on %s (position %s) — not resolvable",
                    comment.get("path"),
                    comment.get("position"),
                )
                failed.append(comment)

        if failed:
            body = "### Comments (could not post inline)\n"
            for c in failed:
                body += f"\n**{c['path']}** {c['body']}\n"
            self.client.post_issue_comment(pr_number=pr_number, body=body)

    def _format_summary(self, review: Review) -> str:
        parts = [
            f"## Review Summary\n\n{review.summary.description}",
        ]

        if review.summary.risks:
            risk_items = "\n".join(f"- {r}" for r in review.summary.risks)
            parts.append(f"\n### Risks\n{risk_items}")

        if review.summary.strengths:
            strength_items = "\n".join(f"- {s}" for s in review.summary.strengths)
            parts.append(f"\n### Strengths\n{strength_items}")

        parts.append(f"\n**Verdict:** {review.summary.verdict}")
        return "\n".join(parts)

    def _try_format_comment(
        self,
        comment: ReviewComment,
        positions: dict[str, dict[int, int]],
    ) -> dict[str, object] | None:
        """Format a comment for the GitHub review API using diff positions.

        Returns None if the comment's line cannot be mapped to a diff position.
        """
        file_positions = positions.get(str(comment.file))
        if not file_positions:
            return None

        # Find the position for the end line (or nearest line in range)
        position = file_positions.get(comment.line_range.end)
        if position is None:
            # Try any line in the range
            for line_no in range(
                comment.line_range.end, comment.line_range.start - 1, -1
            ):
                position = file_positions.get(line_no)
                if position is not None:
                    break

        if position is None:
            return None

        label = _SEVERITY_TO_LABEL.get(comment.severity, SeverityLabel.SUGGESTION)
        body = f"{label} {comment.body}"

        if comment.suggestion:
            body += f"\n\n```suggestion\n{comment.suggestion}\n```"

        return {
            "path": str(comment.file),
            "body": body,
            "position": position,
        }


# =============================================================================
# DIFF PARSING
# =============================================================================

_HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _parse_diff_positions(diff: str) -> dict[str, dict[int, int]]:
    """Parse a unified diff and return {file: {line_number: diff_position}}.

    The position is the 1-based offset from the first ``@@`` header in
    each file's diff section.  GitHub's PR review API uses this value
    for the ``position`` field on inline comments.
    """
    result: dict[str, dict[int, int]] = {}
    current_file: str | None = None
    position = 0
    new_line = 0
    first_hunk_seen = False

    for raw_line in diff.splitlines():
        if raw_line.startswith("diff --git"):
            current_file = None
            first_hunk_seen = False
        elif raw_line.startswith("+++ b/"):
            current_file = raw_line[6:]
            result.setdefault(current_file, {})
        elif raw_line.startswith("@@ ") and current_file is not None:
            match = _HUNK_RE.match(raw_line)
            if match:
                new_line = int(match.group(1))
            if first_hunk_seen:
                # Subsequent @@ headers count as a position
                position += 1
            else:
                # First @@ header resets position counter
                position = 0
                first_hunk_seen = True
        elif current_file is not None and first_hunk_seen:
            position += 1
            if raw_line.startswith("+"):
                # Added line — maps to new file line number
                result[current_file][new_line] = position
                new_line += 1
            elif raw_line.startswith("-"):
                # Deleted line — no new file line, but position advances
                pass
            else:
                # Context line — exists in both old and new file
                result[current_file][new_line] = position
                new_line += 1

    return result
