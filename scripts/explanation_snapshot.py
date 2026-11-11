#!/usr/bin/env python3
"""Render a concise deterministic projection of actual CLI explanation JSON.

Pipe `transist workflows explain --path ... --format json` into this script.
The full CLI report remains authoritative; this projection does not infer prompt
effects, validate readiness, or grant authority. Platform-specific package digests
are retained in full evidence rather than the portable introductory snapshot.
"""

import json
import sys
from typing import Any


def compact(value: Any) -> str:
    """Encode one exact CLI value with stable keys and no platform decoration."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def render(report: dict) -> str:
    """Project authored order, connections, budgets and declared authority as text."""
    if report["schema"] != "transist.workflow_explanation.v1":
        raise ValueError("expected a current CLI explanation report")
    workflow = report["workflow"]
    scope = report["scopes"]["root"]
    lines = [
        f"Workflow: {workflow['id']}@{workflow['version']}",
        f"Definition: {report['definition_sha256']}",
        "Static explanation; authority requested, not granted; "
        "external behavior opaque.",
        "Pins: "
        + ", ".join(
            f"{pin} ({value['status']})" for pin, value in report["pins"].items()
        ),
        "Inputs: "
        + ", ".join(
            f"{name}={value['state']}" for name, value in scope["inputs"].items()
        ),
        "Workspace: " + compact(scope["authority_requests"]["declared"]["workspace"]),
        "Root network: "
        + compact(scope["authority_requests"]["declared"]["workflow_network"]),
        "Documents: " + compact(report["documents"]),
    ]
    for path in scope["step_order"]:
        step = report["steps"][path]
        authority = step["authority_requests"]["declared"]
        lines.append(f"{path}: {step['action']} [{step['behavior']}]")
        lines.append(
            "  network="
            + compact(authority["step_network"])
            + " filesystem="
            + compact(authority["step_filesystem"])
            + " secrets="
            + compact(authority["secret_refs"])
        )
        if step["documents"]:
            lines.append("  documents=" + compact(step["documents"]))
        if step["gate"]:
            lines.append("  gate=" + compact(step["gate"]))
        settings = {
            key: value
            for key, value in step["bound_bindings"].items()
            if key
            in {
                "output_mode",
                "history_mode",
                "max_context_file_bytes",
                "max_prompt_bytes",
                "max_tokens",
                "timeout_ms",
            }
        }
        if settings:
            lines.append("  settings=" + compact(settings))
    lines.append("Cleanup: " + compact(scope["cleanup_order"]))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render(json.load(sys.stdin)))
