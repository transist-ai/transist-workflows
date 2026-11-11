#!/usr/bin/env python3
"""Project a staged attachment tree to bounded lossless file-only model context."""

import base64
import json
from pathlib import Path
import sys


def project(tree: Path, output: Path) -> None:
    """Preserve exact member bytes as base64; fail before provider on overflow."""
    if not tree.is_absolute() or not output.is_absolute() or not tree.is_dir():
        raise ValueError("absolute staged tree and output required")
    members = {}
    for member in sorted(tree.rglob("*")):
        if member.is_symlink() or not (member.is_file() or member.is_dir()):
            raise ValueError("nonregular attachment member")
        if member.is_file():
            if member.stat().st_size > 65536:
                raise ValueError("attachment context exceeds prompt budget")
            members[member.relative_to(tree).as_posix()] = base64.b64encode(
                member.read_bytes()
            ).decode("ascii")
    raw = json.dumps(
        {"encoding": "base64", "members": members}, sort_keys=True
    ).encode()
    if len(raw) > 65536:
        raise ValueError("attachment context exceeds prompt budget")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)


if __name__ == "__main__":
    project(Path(sys.argv[1]), Path(sys.argv[2]))
