#!/usr/bin/env python3
from __future__ import annotations

"""Write bound operator feedback and unresolved PR comments.

Combines two sources:
  1. The current manual-gate reason supplied explicitly by the workflow.
     If the reason is empty, the operator-instructions section is omitted --
     prior iterations' reasons never carry over.
  2. Unresolved PR comments from a review_comments.json artifact
     (passed via --review-comments-file).

Output (operator_feedback.md):
  - If both sources have content: operator instructions first, then a
    formatted list of unresolved PR comments.
  - If only one source has content: just that source.
  - If neither source has content: empty file, signalling to downstream
    steps that no extra operator context was given for this cycle.

When --review-comments-file is omitted the PR-comment section is skipped.
"""

import argparse
import json
import os
import sys
from pathlib import Path

TRANSIST_REVIEW_REPLY_MARKER = "<!-- transist-review-reply -->"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Write operator feedback and unresolved PR comments "
            "to a markdown artifact."
        ),
    )
    parser.add_argument(
        "--review-comments-file",
        default=None,
        help=(
            "Path to review_comments.json. When provided, unresolved PR comments "
            "are included in operator_feedback.md. When omitted or the file is "
            "absent the PR-comment section is skipped."
        ),
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Destination path for the operator_feedback.md artifact.",
    )
    args = parser.parse_args()

    reason = _operator_reason_from_environment()

    pr_comments: list[dict] = []
    if args.review_comments_file:
        pr_comments = _load_pr_comments(Path(args.review_comments_file))

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = _build_content(reason, pr_comments)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    if content.strip():
        print(
            f"Wrote operator feedback ({len(content)} chars, "
            f"{len(pr_comments)} PR comment(s)) to {output_path}",
            file=sys.stderr,
        )
    else:
        print(
            f"No operator feedback; wrote empty file to {output_path}",
            file=sys.stderr,
        )


def _build_content(reason: str, pr_comments: list[dict]) -> str:
    """Combine operator reason and unresolved PR comments into markdown.

    Args:
        reason: Current operator request-change reason (may be empty).
        pr_comments: Filtered list of unresolved PR comment dicts.

    Returns:
        Markdown string to write to operator_feedback.md.
    """
    parts: list[str] = []

    if reason:
        parts.append("## Operator Instructions\n\n" + reason)

    if pr_comments:
        comment_blocks = ["## Unresolved PR Comments\n"]
        for comment in pr_comments:
            source = str(comment.get("source") or "")
            path = str(comment.get("path") or "")
            body = (comment.get("body") or "").strip()
            url = str(comment.get("url") or "")

            if source == "review_thread" and path:
                label = f"`{path}`"
            elif source == "pr_conversation":
                label = "PR conversation"
            else:
                label = "Comment"

            if url:
                header = f"[**{label}**]({url})"
            else:
                header = f"**{label}**"

            comment_blocks.append(f"{header}\n\n{body}")

        parts.append("\n\n".join(comment_blocks))

    return "\n\n".join(parts) + "\n" if parts else ""


def _load_pr_comments(review_comments_file: Path) -> list[dict]:
    """Load unresolved PR comments, skipping Transist follow-up bot replies.

    Args:
        review_comments_file: Path to review_comments.json artifact.

    Returns:
        List of non-bot comment dicts; empty list if file absent or unreadable.
    """
    if not review_comments_file.is_file():
        return []

    try:
        with open(review_comments_file, encoding="utf-8") as fh:
            payload = json.load(fh)
        comments = payload.get("comments") or []
        return [c for c in comments if isinstance(c, dict) and not _is_bot_comment(c)]
    except Exception as exc:
        print(f"Warning: could not read {review_comments_file}: {exc}", file=sys.stderr)
        return []


def _is_bot_comment(comment: dict) -> bool:
    """Return True for Transist-generated follow-up comments.

    Args:
        comment: A single comment dict from review_comments.json.

    Returns:
        True if the comment body starts with the Transist reply marker.
    """
    body = str(comment.get("body") or "")
    return body.lstrip().startswith(TRANSIST_REVIEW_REPLY_MARKER)


def _operator_reason_from_environment() -> str:
    """Return request-change feedback injected by the runtime binding."""
    raw = os.environ.get("TRANSIST_GATE_DECISION_JSON", "").strip()
    if not raw:
        return ""
    try:
        decision = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Warning: invalid gate decision JSON: {exc}", file=sys.stderr)
        return ""
    if not _valid_gate_decision(decision):
        if isinstance(decision, dict) and "review_request" in decision:
            raise ValueError("invalid bound decision with review_request")
        return ""
    if decision.get("decision") != "request_changes":
        return ""
    reason = decision.get("reason")
    return reason.strip() if isinstance(reason, str) else ""


def _valid_gate_decision(decision: object) -> bool:
    """Return whether a value is a complete immutable gate-decision record."""
    if not isinstance(decision, dict):
        return False
    allowed = {
        "schema",
        "run_id",
        "gate_id",
        "step_id",
        "decision",
        "actor",
        "actor_source",
        "reason",
        "decided_at_ms",
        "review_request",
    }
    if set(decision) - allowed:
        return False
    if decision.get("schema") != "transist.gate_decision.v1":
        return False
    for field in ("run_id", "gate_id", "step_id"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            return False
    value = decision.get("decision")
    if not isinstance(value, str) or value not in {
        "approved",
        "rejected",
        "request_changes",
    }:
        return False
    timestamp = decision.get("decided_at_ms")
    if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0:
        return False
    return all(
        field not in decision or isinstance(decision[field], str)
        for field in ("actor", "actor_source", "reason")
    )


if __name__ == "__main__":
    main()
