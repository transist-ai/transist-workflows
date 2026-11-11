#!/usr/bin/env python3
"""Retain deterministic real-CLI delivery explanation snapshots without execution.

Output stays in fresh fixture storage for review. Updating published snapshots is
a separate source edit; this command never overwrites an immutable installation.
"""

import argparse
import hashlib
import json
from pathlib import Path

from check_installed_examples import Driver, ROOT, executable, require
from explanation_snapshot import render

EXAMPLES = ("hotfix_ticket_delivery", "cursor_ticket_delivery")


def main() -> None:
    """Install real selected contracts once per home and explain each source twice."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", type=Path, required=True)
    parser.add_argument("--plugins-dir", type=Path, required=True)
    parser.add_argument("--fixture-base", type=Path, required=True)
    args = parser.parse_args()
    executable(args.transist, "transist")
    for example in EXAMPLES:
        driver = Driver(
            args.transist, args.plugins_dir, args.fixture_base, "explain-" + example
        )
        try:
            path = ROOT / "examples" / example / "workflow.yaml"
            driver.install_plugins(path)
            reports = [
                driver.cli("workflows", "explain", "--path", str(path)).stdout
                for _ in range(2)
            ]
            require(
                reports[0] == reports[1],
                "delivery CLI explanation is not deterministic",
            )
            projection = render(json.loads(reports[0]))
            (driver.root / "explanation.json").write_text(reports[0])
            (driver.root / "explanation.txt").write_text(projection)
            report = json.loads(reports[0])
            snapshot = {
                "workflow": report["workflow"]["id"],
                "version": report["workflow"]["version"],
                "definition_sha256": report["definition_sha256"],
                "projection_sha256": hashlib.sha256(projection.encode()).hexdigest(),
                "projection": "scripts/explanation_snapshot.py",
                "reports_compared": 2,
            }
            (driver.root / "explanation.snapshot.json").write_text(
                json.dumps(snapshot, indent=2) + "\n"
            )
            print(
                example
                + " projection_sha256="
                + hashlib.sha256(projection.encode()).hexdigest(),
                flush=True,
            )
        finally:
            driver.close()


if __name__ == "__main__":
    main()
