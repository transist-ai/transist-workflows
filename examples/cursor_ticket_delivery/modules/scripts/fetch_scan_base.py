#!/usr/bin/env python3
"""Fetch one explicitly authorized branch into its remote-tracking ref."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Iterator


@contextmanager
def fetch_lock(common_dir: Path, timeout: float = 30) -> Iterator[None]:
    """Serialize fetches across worktrees, releasing the lock on process exit."""
    fd = os.open(
        common_dir / ".transist-fetch.lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for shared Git fetch lock")
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def fetch(remote: str, branch: str, pr_file: str = "") -> None:
    """Validate the authorized remote/base and fetch exactly that branch in cwd.

    If supplied, the managed PR file must name that same authorized base. Raises
    on invalid input or Git failure; no branch checkout or working-tree edit occurs.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", remote):
        raise ValueError("invalid remote name")
    if not branch or branch.startswith("-"):
        raise ValueError("invalid authorized base branch")
    source = f"refs/heads/{branch}"
    destination = f"refs/remotes/{remote}/{branch}"
    for ref in (source, destination):
        subprocess.run(["git", "check-ref-format", ref], check=True)
    if pr_file:
        payload = json.loads(Path(pr_file).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(
            payload.get("pull_request"), dict
        ):
            raise ValueError("invalid PR document")
        actual = payload["pull_request"].get("baseRefName")
        if not isinstance(actual, str) or actual != branch:
            raise ValueError("PR base does not match the authorized base branch")
    remotes = subprocess.run(
        ["git", "remote"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    if remote not in remotes:
        raise ValueError("remote is not a configured Git remote")
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not common:
        raise ValueError("missing Git common directory")
    with fetch_lock(Path(common)):
        subprocess.run(
            [
                "git",
                "fetch",
                "--no-tags",
                "--no-recurse-submodules",
                "--",
                remote,
                f"+{source}:{destination}",
            ],
            check=True,
        )


def main() -> None:
    """Parse declared arguments and fetch the authorized branch from Git cwd."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--fallback-branch", default="")
    parser.add_argument("--pr-file", default="")
    args = parser.parse_args()
    fetch(args.remote, args.branch or args.fallback_branch, args.pr_file)


if __name__ == "__main__":
    main()
