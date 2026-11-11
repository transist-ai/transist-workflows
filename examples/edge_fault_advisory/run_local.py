#!/usr/bin/env python3
"""Validate an isolated advisory; execute to review only on explicit request."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

import yaml

EXAMPLE = Path(__file__).resolve().parent
REPO = EXAMPLE.parents[1]
WORKFLOW = "edge_fault_advisory@0.1.0"


def manifest(value: str, plugin_id: str, version: str) -> Path:
    """Read a caller-selected manifest and require its exact package identity."""
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file() or path.name != "plugin.yaml":
        raise ValueError("A regular plugin.yaml manifest is required")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or (
        document.get("schema") != "transist.plugin.v1"
        or document.get("id") != plugin_id
        or document.get("version") != version
    ):
        raise ValueError(f"Expected {plugin_id}@{version}")
    return path


def execute(binary: Path, home: Path, environment: dict[str, str], *args: str) -> str:
    """Run the selected CLI, suppressing potentially unredacted error output."""
    try:
        result = subprocess.run(
            [str(binary), "--home", str(home), *args, "--ui", "plain"],
            env=environment,
            text=True,
            capture_output=True,
            timeout=90,
        )
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(
            "Transist unavailable or timed out; inspect the home"
        ) from None
    if result.returncode:
        raise RuntimeError(
            f"Transist {' '.join(args[:2])} failed; inspect the disposable home"
        )
    return result.stdout


def readiness_report(text: str) -> dict:
    """Require complete successful readiness evidence before creating a run."""
    try:
        report = json.loads(text)
    except ValueError:
        raise RuntimeError("Readiness did not return valid JSON") from None
    if (
        not isinstance(report, dict)
        or report.get("schema") != "transist.workflow_readiness.v1"
        or report.get("status") != "ready"
        or report.get("run_created") is not False
        or not isinstance(report.get("checks"), list)
        or not report["checks"]
        or any(
            not isinstance(check, dict)
            or not (
                check.get("status") == "passed"
                or (
                    check.get("status") == "deferred_to_dispatch"
                    and check.get("code") in {"input_schema", "deferred_to_dispatch"}
                )
            )
            for check in report["checks"]
        )
    ):
        raise RuntimeError("Readiness is incomplete or failed; no run will be started")
    return report


def verify_gate(state: dict) -> None:
    """Require the actual waiting gate and its runtime-owned document review."""
    steps = state.get("steps", {})
    if (
        state.get("status") != "blocked"
        or steps.get("diagnostic_transfer", {}).get("status") != "blocked"
    ):
        raise RuntimeError("Run did not stop at the diagnostic transfer gate")
    request = (
        steps.get("diagnostic_transfer", {})
        .get("last_result", {})
        .get("output", {})
        .get("review_request", {})
    )
    documents = request.get("review_documents", [])
    if (
        request.get("step_id") != "diagnostic_transfer"
        or request.get("gate_id") != "diagnostic-transfer"
        or len(documents) != 1
        or documents[0].get("document") != "diagnostic"
        or not documents[0].get("revision_id")
        or not documents[0].get("blob", {}).get("sha256")
    ):
        raise RuntimeError("Missing diagnostic document review; do not approve")


def main(argv: list[str] | None = None) -> int:
    """Install/check in fresh storage; --execute starts a run but never approves."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--shell-manifest", required=True)
    parser.add_argument("--openai-manifest", required=True)
    parser.add_argument("--workspace", type=Path, default=EXAMPLE / "fixtures")
    parser.add_argument("--diagnostic-path", default="diagnostics.txt")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly approve local capture/start, stopping at document review",
    )
    args = parser.parse_args(argv)
    if not args.model.strip():
        parser.error("--model must be nonempty")
    try:
        binary = args.transist.expanduser().resolve(strict=True)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError("--transist must select an executable")
        shell = manifest(args.shell_manifest, "shell", "0.1.0")
        openai = manifest(args.openai_manifest, "openai.compatible", "0.1.0")
        workspace = args.workspace.expanduser().resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("--workspace must select an existing directory")
        version = subprocess.run(
            [str(binary), "--version"],
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
        ).stdout.strip()
        if version != "transist 0.1.1":
            raise ValueError("This example requires the tested Transist 0.1.1 release")
    except (OSError, ValueError, yaml.YAMLError, subprocess.SubprocessError):
        parser.error("Runtime or exact plugin prerequisite is invalid")
    temp_root = REPO / "tmp"
    if temp_root.is_symlink():
        parser.error("The disposable-home directory must not be a symlink")
    temp_root.mkdir(exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="edge-fault-", dir=temp_root)) / "home"
    # Print the location even if installation or readiness fails; never print keys.
    print(f"Disposable home: {home}", flush=True)
    environment = os.environ.copy()
    execute(binary, home, environment, "home", "init", "--mode", "standalone")
    config_path = home / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["policy"]["remote_secret_delivery"]["process"] = True
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    for plugin in (shell, openai):
        execute(binary, home, environment, "plugins", "install", "--path", str(plugin))
    inputs = (
        "--input",
        f"workspace_path={workspace}",
        "--input",
        f"model={args.model}",
        "--input",
        f"diagnostic_path={args.diagnostic_path}",
    )
    # Source validation does not require credentials, probe a provider or read data.
    execute(
        binary,
        home,
        environment,
        "workflows",
        "check",
        "--path",
        str(EXAMPLE / "workflow.yaml"),
        "--format",
        "json",
        *inputs,
    )
    if not args.execute:
        print(
            "Source validated. No run created. Use --execute for local capture/review."
        )
        return 0
    if not os.environ.get("OPENAI_COMPATIBLE_API_KEY"):
        raise RuntimeError("OPENAI_COMPATIBLE_API_KEY is required for live readiness")
    execute(
        binary,
        home,
        environment,
        "workflows",
        "install",
        "--path",
        str(EXAMPLE / "workflow.yaml"),
        "--approve",
    )
    readiness_report(
        execute(
            binary,
            home,
            environment,
            "workflows",
            "check",
            WORKFLOW,
            "--live",
            "--format",
            "json",
            *inputs,
        )
    )
    run_id = "edge_fault_" + uuid.uuid4().hex[:12]
    execute(
        binary,
        home,
        environment,
        "workflows",
        "run",
        WORKFLOW,
        "--run-ref",
        run_id,
        *inputs,
    )
    for _ in range(100):
        state = json.loads(
            execute(
                binary, home, environment, "runs", "show", run_id, "--format", "json"
            )
        )
        if state.get("status") in (
            "blocked",
            "failed",
            "success",
            "canceled",
        ):
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Run did not reach review; inspect the disposable home")
    verify_gate(state)
    print(f"Run: {run_id}")
    print(f"Review with the selected CLI: --home {home} runs show {run_id}")
    print(
        "Use runs gate approve/reject with actor and reason "
        "after reviewing the payload."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
