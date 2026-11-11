#!/usr/bin/env python3
"""Prevent exhausted implementation review from advancing without approval."""

from __future__ import annotations

import sys


def main(args: list[str]) -> int:
    """Accept only the current gate's approved decision; otherwise fail closed."""
    if args == ["approved"]:
        return 0
    print("Implementation review did not approve the changes", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
