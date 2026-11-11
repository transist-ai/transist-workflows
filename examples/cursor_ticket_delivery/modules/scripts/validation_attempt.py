#!/usr/bin/env python3
"""Maintain bounded remediation bookkeeping in an explicitly staged document."""

import argparse
import json
from pathlib import Path


def advance(path: Path, maximum: int) -> int:
    """Increment exact current document state; return the new attempt number."""
    if maximum < 1 or maximum > 5:
        raise ValueError("max attempts must be between 1 and 5")
    state = json.loads(path.read_bytes())
    if set(state) != {"attempt"} or type(state["attempt"]) is not int:
        raise ValueError("invalid remediation state")
    if not 0 <= state["attempt"] < maximum:
        raise ValueError("remediation attempts exhausted")
    state["attempt"] += 1
    path.write_text(json.dumps(state) + "\n")
    return state["attempt"]


def main() -> None:
    """Update private staged bookkeeping; no ticket/path-derived state lookup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--max-attempts", required=True, type=int)
    args = parser.parse_args()
    print(advance(args.file, args.max_attempts))


if __name__ == "__main__":
    main()
