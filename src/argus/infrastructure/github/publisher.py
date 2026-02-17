"""GitHub PR review publisher."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.review.entities import Review, ReviewComment
from argus.infrastructure.constants import SeverityLabel
from argus.infrastructure.github.client import GitHubClient
from argus.shared.types import Severity

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

    def publish(self, review: Review, pr_number: int) -> None:
        """Post a review to a pull request.

        Posts the summary as the review body and each comment as an
        inline review comment at the appropriate file and line.
        """
        summary_text = self._format_summary(review)
        inline_comments = [self._format_comment(c) for c in review.comments]

        if inline_comments:
            self.client.post_review(
                pr_number=pr_number,
                body=summary_text,
                comments=inline_comments,
            )
        else:
            self.client.post_issue_comment(
                pr_number=pr_number,
                body=summary_text,
            )

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

    def _format_comment(self, comment: ReviewComment) -> dict[str, object]:
        label = _SEVERITY_TO_LABEL.get(comment.severity, SeverityLabel.SUGGESTION)
        body = f"{label} {comment.body}"

        if comment.suggestion:
            body += f"\n\n**Suggestion:** {comment.suggestion}"

        result: dict[str, object] = {
            "path": str(comment.file),
            "body": body,
            "line": comment.line_range.end,
        }

        if comment.line_range.start != comment.line_range.end:
            result["start_line"] = comment.line_range.start

        return result
