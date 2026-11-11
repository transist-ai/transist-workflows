#!/usr/bin/env python3
"""Reject stageable legacy operational files without configuring target ignores.

Current operational data uses managed documents outside the workspace. This
read-only defense still rejects old .transist or interaction files that an
all-changes commit could otherwise publish. No ignore rule is required for an
empty workspace, and this helper never edits ignore files or the index.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def operational(path: Path) -> bool:
    """Return whether a Git-relative path is working storage or an interaction."""
    return ".transist" in path.parts or path.name.endswith(
        (".interaction.json", ".interaction.md")
    )


def git(root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a read-only Git query in the exact target workspace with a timeout."""
    return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)


def check(root: Path) -> None:
    """Require the exact Git worktree root and reject stageable operational files."""
    root = root.resolve(strict=True)
    prefix = git(root, ["rev-parse", "--show-prefix"])
    if prefix.returncode or prefix.stdout.strip():
        raise ValueError("workspace must be the Git worktree root")
    tracked = git(
        root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    if tracked.returncode:
        raise ValueError("cannot inspect tracked working files")
    for name in tracked.stdout.decode("utf-8").split("\0"):
        if name and operational(Path(name)):
            raise ValueError(
                "tracked or unignored operational files cannot enter a commit"
            )


def main() -> int:
    """Check caller-selected storage without exposing operational paths or contents."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", required=True)
    args = parser.parse_args()
    try:
        check(Path(args.repo_path))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, ValueError) else "Git query failed"
        print(f"Working files: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
