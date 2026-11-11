#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render PR validation-awareness comment body.",
    )
    parser.add_argument("--status", choices=["failed", "resolved"], required=True)
    parser.add_argument("--validation-report-file", required=True)
    parser.add_argument("--output-file", required=True)
    return parser.parse_args()


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        return handle.read()


def extract_verdict(report_text: str) -> str:
    lines = report_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## verdict":
            following_index = index + 1
            for candidate in lines[following_index:]:
                cleaned = candidate.strip()
                if cleaned:
                    return cleaned
            break
    for line in lines:
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return "Unavailable"


def build_body(status: str, verdict: str) -> str:
    if status == "failed":
        return (
            "OpenSpec validation mismatch detected before exiting "
            "the PR review loop.\n\n"
            f"- Latest verdict: {verdict}\n"
            "- Action: review `validation_report.md`, then choose whether "
            "to exit or request more changes."
        )
    return (
        "OpenSpec validation now passes for the current PR state.\n\n"
        f"- Latest verdict: {verdict}\n"
        "- Status: mismatch resolved."
    )


def main() -> int:
    args = parse_args()
    report_path = Path(args.validation_report_file).resolve()
    output_path = Path(args.output_file).resolve()

    report_text = read_text(report_path)
    verdict = extract_verdict(report_text)
    body = build_body(args.status, verdict)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(body.strip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
