"""Tests for GitHub review publisher."""

from __future__ import annotations

from unittest.mock import MagicMock

from argus.domain.review.entities import Review, ReviewComment
from argus.domain.review.value_objects import ReviewSummary
from argus.infrastructure.constants import SeverityLabel
from argus.infrastructure.github.publisher import (
    GitHubReviewPublisher,
    _parse_diff_positions,
)
from argus.shared.exceptions import PublishError
from argus.shared.types import Category, FilePath, LineRange, Severity

# =============================================================================
# Helpers
# =============================================================================

# Hunk: +8,12 means new file lines 8-19
# Position layout:
#   pass       → pos 1, line 8 (context)
#   pass       → pos 2, line 9 (context)
#   +new_10    → pos 3, line 10
#   +new_11    → pos 4, line 11
#   +new_12    → pos 5, line 12
#   +new_13    → pos 6, line 13
#   +new_14    → pos 7, line 14
#   +new_15    → pos 8, line 15
SAMPLE_DIFF = """\
--- a/src/main.py
+++ b/src/main.py
@@ -8,6 +8,12 @@ def existing():
     pass
     pass
+    new_line_10 = True
+    new_line_11 = True
+    new_line_12 = True
+    new_line_13 = True
+    new_line_14 = True
+    new_line_15 = True
"""


def _make_review(
    comments: list[ReviewComment] | None = None,
) -> Review:
    return Review(
        summary=ReviewSummary(
            description="Looks good overall.",
            risks=["May break on edge cases"],
            strengths=["Clean code"],
            verdict="Approve with suggestions",
        ),
        comments=comments or [],
    )


def _make_comment(
    severity: Severity = Severity.WARNING,
    file: str = "src/main.py",
    start: int = 10,
    end: int = 15,
) -> ReviewComment:
    return ReviewComment(
        file=FilePath(file),
        line_range=LineRange(start=start, end=end),
        severity=severity,
        category=Category.BUG,
        body="This could be an issue.",
        confidence=0.85,
        suggestion="Consider adding a null check.",
    )


# =============================================================================
# Tests — inline comments (lines in diff)
# =============================================================================


def test_publish_with_comments_in_diff_uses_post_review() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)
    review = _make_review(comments=[_make_comment()])

    publisher.publish(review, pr_number=42)

    mock_client.post_review.assert_called_once()


def test_publish_without_comments_uses_issue_comment() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)
    review = _make_review(comments=[])

    publisher.publish(review, pr_number=42)

    mock_client.post_issue_comment.assert_called_once()
    mock_client.post_review.assert_not_called()


def test_publish_formats_summary_correctly() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)
    review = _make_review()

    publisher.publish(review, pr_number=42)

    body = mock_client.post_issue_comment.call_args.kwargs["body"]
    assert "Looks good overall." in body
    assert "May break on edge cases" in body
    assert "Clean code" in body
    assert "Approve with suggestions" in body


def test_publish_formats_comment_with_severity_label() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    comment = _make_comment(severity=Severity.CRITICAL)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted_comments = mock_client.post_review.call_args.kwargs["comments"]
    assert len(posted_comments) == 1
    assert SeverityLabel.CRITICAL in posted_comments[0]["body"]


def test_publish_includes_suggestion_in_comment() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    comment = _make_comment()
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted_comments = mock_client.post_review.call_args.kwargs["comments"]
    assert "Suggestion:" in posted_comments[0]["body"]


def test_publish_comment_uses_position() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    # Single-line comment on line 10 → position 3
    comment = _make_comment(start=10, end=10)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted = mock_client.post_review.call_args.kwargs["comments"][0]
    assert posted["position"] == 3
    assert posted["path"] == "src/main.py"


def test_publish_comment_uses_end_line_position() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    # Multi-line comment: lines 10-15, end line 15 -> position 8
    comment = _make_comment(start=10, end=15)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    posted = mock_client.post_review.call_args.kwargs["comments"][0]
    assert posted["position"] == 8


# =============================================================================
# Tests — comments outside diff go to body
# =============================================================================


def test_comments_outside_diff_go_to_body() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    comment = _make_comment(file="other_file.py", start=1, end=1)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    mock_client.post_issue_comment.assert_called_once()
    body = mock_client.post_issue_comment.call_args.kwargs["body"]
    assert "other_file.py:1" in body
    assert "This could be an issue." in body


def test_no_diff_puts_all_comments_in_body() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client)  # no diff

    comment = _make_comment()
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    mock_client.post_issue_comment.assert_called_once()
    body = mock_client.post_issue_comment.call_args.kwargs["body"]
    assert "src/main.py:10" in body


def test_line_outside_hunk_goes_to_body() -> None:
    mock_client = MagicMock()
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    # Line 50 is not in the hunk (8-19)
    comment = _make_comment(start=50, end=50)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    mock_client.post_issue_comment.assert_called_once()
    mock_client.post_review.assert_not_called()


def test_fallback_posts_comments_individually() -> None:
    mock_client = MagicMock()
    mock_client.post_review.side_effect = [
        PublishError("422"),
        None,  # individual comment succeeds
    ]
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    comment = _make_comment()
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    mock_client.post_issue_comment.assert_called_once()
    assert mock_client.post_review.call_count == 2


def test_fallback_collects_failed_individual_comments() -> None:
    mock_client = MagicMock()
    mock_client.post_review.side_effect = PublishError("422")
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    comment = _make_comment()
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    # Summary + failed comments body
    assert mock_client.post_issue_comment.call_count == 2


# =============================================================================
# Tests — diff position parsing
# =============================================================================


def test_parse_positions_single_hunk() -> None:
    result = _parse_diff_positions(SAMPLE_DIFF)

    assert "src/main.py" in result
    pos = result["src/main.py"]
    # Context lines
    assert pos[8] == 1  # pass
    assert pos[9] == 2  # pass
    # Added lines
    assert pos[10] == 3
    assert pos[11] == 4
    assert pos[15] == 8


def test_parse_positions_new_file() -> None:
    diff = """\
diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+line1
+line2
+line3
"""
    result = _parse_diff_positions(diff)
    pos = result["new.py"]
    assert pos[1] == 1
    assert pos[2] == 2
    assert pos[3] == 3


def test_parse_positions_multiple_hunks() -> None:
    diff = """\
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@ header
 ctx1
+added
 ctx2
 ctx3
@@ -10,3 +11,4 @@ second
 ctx10
+added2
 ctx11
"""
    result = _parse_diff_positions(diff)
    pos = result["file.py"]

    # First hunk
    assert pos[1] == 1  # ctx1
    assert pos[2] == 2  # +added
    assert pos[3] == 3  # ctx2
    assert pos[4] == 4  # ctx3

    # Second @@ header counts as position 5
    assert pos[11] == 6  # ctx10
    assert pos[12] == 7  # +added2
    assert pos[13] == 8  # ctx11


def test_parse_positions_deleted_lines_dont_map() -> None:
    diff = """\
--- a/file.py
+++ b/file.py
@@ -1,4 +1,3 @@
 ctx
-removed
 after1
 after2
"""
    result = _parse_diff_positions(diff)
    pos = result["file.py"]
    assert pos[1] == 1  # ctx (position 1)
    # position 2 is the "-removed" line — no new file line
    assert pos[2] == 3  # after1
    assert pos[3] == 4  # after2


def test_parse_positions_multiple_files() -> None:
    diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
 ctx
+added
 ctx2
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1,2 +1,3 @@
 ctx
+added
 ctx2
"""
    result = _parse_diff_positions(diff)
    # Each file has independent positions
    assert result["a.py"][2] == 2  # +added
    assert result["b.py"][2] == 2  # +added


def test_comment_line_falls_back_to_nearest_in_range() -> None:
    """If the exact end line has no position, try earlier lines."""
    mock_client = MagicMock()
    # Hunk covers lines 8-15 only
    publisher = GitHubReviewPublisher(client=mock_client, diff=SAMPLE_DIFF)

    # Comment on lines 10-20: line 20 is not in diff, but line 15 is
    comment = _make_comment(start=10, end=20)
    review = _make_review(comments=[comment])

    publisher.publish(review, pr_number=42)

    # Should still post as inline, using nearest line in range
    mock_client.post_review.assert_called_once()
    posted = mock_client.post_review.call_args.kwargs["comments"][0]
    assert posted["position"] == 8  # line 15's position
