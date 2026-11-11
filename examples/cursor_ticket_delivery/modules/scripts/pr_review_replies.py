#!/usr/bin/env python3
"""Workflow-specific review projection and formatting of explicit reply outcomes.

All paths are staged data. This helper has no provider commands or publication
mode: GitHub delivery/reconciliation belongs to github.cli, never a shell helper.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

TRANSIST_REVIEW_REPLY_MARKER = "<!-- transist-review-reply -->"
REVIEW_REPLIES_HEADING_RE = re.compile(r"(?mi)^##\s+Review Replies\s*$")
FENCED_JSON_BLOCK_RE = re.compile(r"(?ms)^\s*```(?:json)?\s*\n(.*?)\n```")
SLASH_COMMAND_RE = re.compile(r"^/[A-Za-z][A-Za-z0-9_-]*(?:\s|$)")
MAX_BYTES = 65536


def compact_text(value: Any) -> str:
    """Retain the existing reply formatting: compact whitespace into one line."""
    return " ".join(str(value or "").split())


def is_ignorable_comment(comment: dict) -> bool:
    """Exclude only Transist replies and a leading slash command, not !!! requests."""
    body = str(comment.get("body") or "")
    if body.lstrip().startswith(TRANSIST_REVIEW_REPLY_MARKER):
        return True
    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    return SLASH_COMMAND_RE.match(first) is not None


def filter_review_comments_payload(
    payload: dict, replied_to_ids: set[str] | None = None
) -> dict:
    """Project exact request/location text once, without transport/diff duplicates."""
    fields = {
        "id",
        "source",
        "author",
        "body",
        "path",
        "line",
        "original_line",
        "side",
        "start_line",
        "url",
        "thread_id",
        "review_comment_id",
        "created_at",
        "outdated",
        "diff_hunk_header",
    }
    comments = payload.get("comments") or []
    filtered = []
    for comment in comments:
        if (
            not isinstance(comment, dict)
            or is_ignorable_comment(comment)
            or compact_text(comment.get("id")) in (replied_to_ids or set())
        ):
            continue
        projected = {key: value for key, value in comment.items() if key in fields}
        if "diff_hunk_header" in comment:
            # Step 7 has already projected away diff_hunk. Its schema permits a
            # string header; retain those exact bytes, including when line is null.
            header = comment["diff_hunk_header"]
            if not isinstance(header, str) or len(header.encode("utf-8")) > MAX_BYTES:
                raise ValueError("invalid or oversized projected diff header")
        else:
            # Direct raw-input callers may still derive only the bounded header,
            # never copy a full diff body into model context.
            header = re.search(
                r"(?m)^(@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)",
                str(comment.get("diff_hunk") or ""),
            )
            if header:
                projected["diff_hunk_header"] = header[1]
        filtered.append(projected)
    return {
        "comments": filtered,
        "count": len(filtered),
        "review_thread_comment_count": sum(
            c.get("source") == "review_thread" for c in filtered
        ),
        "pr_conversation_comment_count": sum(
            c.get("source") == "pr_conversation" for c in filtered
        ),
        "filtered_out_count": max(0, len(comments) - len(filtered)),
    }


def extract_review_reply_entries(markdown: str) -> list[dict]:
    """Require exactly one JSON response array in its own Review Replies section."""
    heading = REVIEW_REPLIES_HEADING_RE.search(markdown)
    if heading is None:
        raise ValueError("implementation notes must contain `## Review Replies`")
    section_start = heading.end()
    tail = markdown[section_start:]
    next_heading = re.search(r"(?m)^##\s+", tail)
    if next_heading:
        tail = tail[: next_heading.start()]
    blocks = list(FENCED_JSON_BLOCK_RE.finditer(tail))
    if len(blocks) != 1:
        raise ValueError(
            "`## Review Replies` must contain exactly one fenced JSON array"
        )
    value = json.loads(blocks[0].group(1))
    if not isinstance(value, list):
        raise ValueError("`## Review Replies` must be a JSON array")
    return value


def actionable_comments_by_id(payload: dict) -> dict[str, dict]:
    """Index exact actionable request identities for complete outcome validation."""
    result = {}
    for comment in payload.get("comments") or []:
        if not isinstance(comment, dict) or is_ignorable_comment(comment):
            continue
        identity = compact_text(comment.get("id"))
        if identity:
            result[identity] = comment
    return result


def build_review_reply_plan(
    review_comments_payload: dict, implementation_notes_markdown: str
) -> dict:
    """Require every explicit outcome; resolve only fully addressed thread groups.

    Clarification/rejection replies are published by the plugin. Thread resolution
    additionally requires an actual committed change, bound as a real Boolean by
    the workflow. No outcome creates authority or a provider effect here.
    """
    comments = actionable_comments_by_id(review_comments_payload)
    outcomes = {}
    responses = []
    comment_outcomes = []
    for index, entry in enumerate(
        extract_review_reply_entries(implementation_notes_markdown), 1
    ):
        if not isinstance(entry, dict):
            raise ValueError(f"Review reply entry #{index} must be an object")
        identity = compact_text(entry.get("comment_id"))
        reply = compact_text(entry.get("reply"))
        outcome = entry.get("outcome")
        if not isinstance(entry.get("comment_id"), str) or not identity:
            raise ValueError("missing comment_id")
        if not isinstance(entry.get("reply"), str) or not reply:
            raise ValueError("missing reply")
        if outcome not in ("addressed", "clarification", "rejected"):
            raise ValueError("invalid outcome")
        if identity in outcomes:
            raise ValueError("Duplicate review reply entry for comment_id " + identity)
        if identity not in comments:
            raise ValueError(
                "Review reply entry references unknown or filtered comment_id "
                + identity
            )
        outcomes[identity] = outcome
        comment_outcomes.append(
            {"comment_id": identity, "outcome": outcome, "reply": reply}
        )
        if outcome != "addressed":
            comment = comments[identity]
            responses.append(
                {
                    "comment_id": identity,
                    "reply": reply,
                    **{
                        key: compact_text(comment.get(key))
                        for key in (
                            "source",
                            "author",
                            "url",
                            "thread_id",
                            "review_comment_id",
                        )
                    },
                }
            )
    missing = set(comments) - set(outcomes)
    if missing:
        raise ValueError(
            "Missing explicit review outcomes for comment_id(s): "
            + ", ".join(sorted(missing))
        )
    threads: dict[str, list[str]] = {}
    for identity, comment in comments.items():
        thread = compact_text(comment.get("thread_id"))
        if comment.get("source") == "review_thread" and thread:
            threads.setdefault(thread, []).append(outcomes[identity])
    return {
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "actionable_comment_count": len(comments),
        "count": len(responses),
        "addressed_thread_ids": [
            key
            for key, values in threads.items()
            if all(value == "addressed" for value in values)
        ],
        "comment_outcomes": comment_outcomes,
        "responses": responses,
    }


def read(path: Path) -> bytes:
    """Read a bounded regular staged file, rejecting symlink/path confusion."""
    if (
        not path.is_absolute()
        or ".." in path.parts
        or any(p.is_symlink() for p in (path, *path.parents))
        or not path.is_file()
    ):
        raise ValueError("regular absolute staged input required")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("review context exceeds 64 KiB; no requests were dropped")
    return raw


def write(path: Path, value: dict) -> None:
    """Write a complete bounded JSON output to the private invocation copy."""
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("review context exceeds 64 KiB; no requests were dropped")
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("absolute staged output required")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def main() -> int:
    """Filter context or format a reply plan; all external work stays in plugins."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    project = commands.add_parser("filter")
    project.add_argument("--input-file", required=True, type=Path)
    project.add_argument("--state-file", type=Path)
    project.add_argument("--pr-file", type=Path)
    project.add_argument("--output-file", required=True, type=Path)
    plan = commands.add_parser("plan")
    plan.add_argument("--review-comments-file", required=True, type=Path)
    plan.add_argument("--implementation-notes-file", required=True, type=Path)
    plan.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "filter":
            state = (
                json.loads(read(args.state_file))
                if args.state_file
                else {"responses": {}}
            )
            if not isinstance(state, dict) or not isinstance(
                state.get("responses"), dict
            ):
                raise ValueError("invalid reply publication state")
            value = filter_review_comments_payload(
                json.loads(read(args.input_file)), set(state["responses"])
            )
            if args.pr_file:
                pr = json.loads(read(args.pr_file))
                pr = pr.get("pull_request", pr)
                if not isinstance(pr, dict):
                    raise ValueError("invalid current PR state")
                value["pull_request"] = {
                    key: pr[key]
                    for key in ("number", "state", "url", "title")
                    if key in pr
                }
        else:
            value = build_review_reply_plan(
                json.loads(read(args.review_comments_file)),
                read(args.implementation_notes_file).decode(),
            )
        write(args.output_file, value)
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
