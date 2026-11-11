#!/usr/bin/env python3
"""Copy exact runtime-reviewed staged bytes to root-shared handoff documents."""

from pathlib import Path
import sys


def main(args: list[str]) -> None:
    """Copy source/destination pairs; approval is enforced on the source bindings."""
    if not args or len(args) % 2:
        raise ValueError("source/destination pairs required")
    for source, destination in zip(args[::2], args[1::2]):
        src, dst = Path(source), Path(destination)
        if not src.is_absolute() or not dst.is_absolute() or not src.is_file():
            raise ValueError("regular staged source and absolute destination required")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())


if __name__ == "__main__":
    main(sys.argv[1:])
