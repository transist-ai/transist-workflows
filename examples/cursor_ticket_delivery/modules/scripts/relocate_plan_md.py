#!/usr/bin/env python3
"""Place plan.md next to tasks.md after plan approval.

The source is a private managed-document read whose exact revision the runtime
checks against the recipe-local plan-review gate. Copy it into the intentional
workspace OpenSpec change bundle beside tasks.md, proposal.md and design.md.
Later modules use managed approved handoffs, never this invocation's source path.

The source is a required runtime-reviewed staged document on every invocation.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys


def sanitize_slug(raw: str) -> str:
    """Match OpenSpec's deterministic change-name slug for the workspace bundle."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(raw or "").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "change"


def resolve_plan_dir(args: argparse.Namespace) -> str:
    """Return the workspace deliverable directory, not operational storage."""
    if args.plan_dir:
        return os.path.abspath(os.path.expanduser(args.plan_dir))
    repo_path = os.path.abspath(os.path.expanduser(args.repo_path))
    return os.path.join(
        repo_path, "openspec", "changes", sanitize_slug(args.change_name)
    )


def main() -> int:
    """Copy required reviewed source bytes to the selected OpenSpec deliverable."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan-file",
        required=True,
        help="Current plan.md path (response_file location).",
    )
    parser.add_argument(
        "--plan-dir", default="", help="Target directory (where tasks.md lives)."
    )
    parser.add_argument(
        "--repo-path",
        default="",
        help="Repo path; used with --change-name when --plan-dir is empty.",
    )
    parser.add_argument(
        "--change-name",
        default="",
        help="OpenSpec change name; slugged to compute the target dir.",
    )
    parser.add_argument("--plan-filename", default="plan.md")
    args = parser.parse_args()

    if not args.plan_dir and not (args.repo_path and args.change_name):
        print(
            "either --plan-dir or both --repo-path and --change-name are required",
            file=sys.stderr,
        )
        return 2

    source = os.path.abspath(os.path.expanduser(args.plan_file))
    plan_dir = resolve_plan_dir(args)
    destination = os.path.join(plan_dir, args.plan_filename)

    if os.path.normpath(source) == os.path.normpath(destination):
        return 0

    if not os.path.isfile(source):
        print(f"plan.md source missing: {source}", file=sys.stderr)
        return 1

    os.makedirs(plan_dir, exist_ok=True)
    shutil.copyfile(source, destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
