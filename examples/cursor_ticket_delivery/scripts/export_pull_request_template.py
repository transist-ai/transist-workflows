#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy a repo-local pull request template into a workflow artifact. "
            "Only /.github/pull_request_template.md is recognized."
        )
    )
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-file", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_path = Path(args.repo_path)
    output_file = Path(args.output_file)
    template_path = repo_path / ".github" / "pull_request_template.md"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    if template_path.is_file():
        output_file.write_text(
            template_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    else:
        output_file.write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
