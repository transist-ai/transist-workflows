"""Exact current-byte provenance, including staged repositories without a commit."""

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

from check_public_snapshot import candidate_files


def read_regular(root: Path, relative: Path) -> tuple[bytes, int]:
    """Read contained regular bytes/mode through no-follow POSIX directory handles."""
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("unsafe inventory path")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            following = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = following
        descriptor = os.open(
            relative.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("inventory requires regular files")
            content = handle.read()
            after = os.fstat(handle.fileno())
            if (metadata.st_size, metadata.st_mtime_ns, metadata.st_mode) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_mode,
            ):
                raise ValueError("source changed while reading")
            return content, metadata.st_mode & 0o777
    finally:
        os.close(directory)


def inventory(files: dict[Path, tuple[bytes, int]]) -> dict:
    """Return sorted path/content/Git-mode records and their canonical JSON digest."""
    records = [
        {
            "path": path.as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mode": "100755" if mode & 0o111 else "100644",
        }
        for path, (content, mode) in sorted(files.items())
    ]
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {"files": records, "sha256": hashlib.sha256(encoded).hexdigest()}


def source_identity(root: Path) -> dict:
    """Record current inventory, status and optional HEAD; never require old history."""

    def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        """Read Git metadata with bounded execution and captured diagnostics."""
        return subprocess.run(
            ["git", *arguments], cwd=root, check=check, capture_output=True, timeout=30
        )

    head = git("rev-parse", "--verify", "--quiet", "HEAD", check=False)
    if head.returncode:
        git("symbolic-ref", "--quiet", "HEAD")
    paths = [Path(p) for p in candidate_files(root)]
    result = inventory({p: read_regular(root, p) for p in paths})
    result.update(
        head=head.stdout.decode().strip() if head.returncode == 0 else None,
        status=git("status", "--porcelain=v1").stdout.decode(),
    )
    return result
