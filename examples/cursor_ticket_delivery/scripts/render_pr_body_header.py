#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render deterministic header lines for PR body drafting."
    )
    parser.add_argument("--jira-ticket-id", required=True)
    parser.add_argument("--jira-site-url", default="")
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--plan-doc-url-file", default="")
    parser.add_argument("--plan-doc-label", default="README")
    parser.add_argument("--plan-doc-prefix", default="Development plan")
    return parser.parse_args()


def render_addresses_line(ticket_id: str, site_url: str) -> str:
    site_url = site_url.rstrip("/")
    if site_url:
        return f"Addresses: [{ticket_id}]({site_url}/browse/{ticket_id})"
    return f"Addresses: {ticket_id}"


def main() -> int:
    args = parse_args()
    output_file = Path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    lines = [render_addresses_line(args.jira_ticket_id, args.jira_site_url)]

    if args.plan_doc_url_file:
        plan_doc_url = Path(args.plan_doc_url_file).read_text(encoding="utf-8").strip()
        if plan_doc_url:
            lines.append(
                f"{args.plan_doc_prefix}: [{args.plan_doc_label}]({plan_doc_url})"
            )

    output_file.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
