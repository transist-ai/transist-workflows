#!/usr/bin/env python3
"""Publish exact reviewed bytes to named root-shared handoff documents.

The runtime enforces each source binding's recipe-local reviewed_by approval.
This data-only helper copies pairs of staged source/destination paths. It does
not infer or grant approval, select a workspace, or contact a provider.
"""

from pathlib import Path
import sys


def main(args: list[str]) -> None:
    """Copy source/destination pairs; fail if any input is missing or nonregular."""
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
