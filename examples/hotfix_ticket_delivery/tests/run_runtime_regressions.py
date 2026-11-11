#!/usr/bin/env python3
"""Explicit, offline integration runner; intentionally not unittest-discovered.

Run with --transist, --shell-plugin and --fixture-base (approved disposable tmp).
Requires PyYAML in the controller only. Retains fresh standalone homes, copied
source, command transcripts, document evidence and summary.json. No operational
home, signing, credentials, provider, remote Git or branch operations are used.
The real working-file guard reads an empty, unborn fixture Git repository.

Only external model/scanner/cleanup actions are replaced with shell producers in
the copied graphs. Root orchestration is a minimal fragment with the original
document declarations and cleanup conditions. Synthetic decisions authorize only
these fixtures. Every failure is nonzero; missing prerequisites are never skips.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any

TERMINAL = {"success", "failed", "canceled"}
CASES = ("approve", "request-changes", "reject", "early-failure", "iteration-limit")
TST = "# TST: preserve exact synthetic feedback — iteration one\n"
REASON = "Synthetic reviewer: handle the boundary case — keep exact text."
APPROVED_IMPLEMENTATION = {"approved_notes", "approved_summary", "approved_pr_body"}


def require(condition: Any, message: str) -> None:
    """Fail a regression assertion with an actionable diagnostic."""
    if not condition:
        raise AssertionError(message)


def read_json(path: Path) -> Any:
    """Decode retained fixture JSON without modifying it."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    """Write human-readable JSON evidence to fixture-owned storage."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path: Path) -> str:
    """Return the SHA-256 identity of a selected source or payload file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic(args: list[str]) -> int:
    """Implement deterministic shell actions inside the real runtime sandbox."""
    operation, *values = args
    events_path = Path.cwd() / "events.jsonl"
    events = (
        [json.loads(line) for line in events_path.read_text().splitlines()]
        if events_path.exists()
        else []
    )
    metadata = read_json(Path(os.environ["TRANSIST_RUNTIME_METADATA_FILE"]))
    event = {"operation": operation, "run_id": metadata["run"]["id"]}
    if operation == "seed":
        for name in values:
            Path(name).write_text("synthetic local context\n")
    elif operation == "model":
        _fail, count, tst_index, *names = values
        paths = list(map(Path, names))
        context_count = int(count)
        contexts = paths[:context_count]
        context, issue, attachments = contexts[:3]
        tst = contexts[int(tst_index)]
        notes, title, body = paths[context_count:]
        number = 1 + sum(item["operation"] == "model" for item in events)
        event.update(
            iteration=number,
            ledger=[json.loads(line) for line in context.read_text().splitlines()],
            tst=tst.read_text(),
            prior_notes=notes.read_text(),
            issue=issue.read_text(),
            attachments=attachments.read_text(),
            additional_context=[path.read_text() for path in contexts[3:]],
        )
        # Even the failing producer writes staged outputs: none may be published.
        notes.write_text(event["prior_notes"] + f"Implementation {number}\n")
        title.write_text(f"Synthetic change {number}\n")
        body.write_text(f"PR draft {number}\n")
    elif operation == "scan":
        Path(values[0]).write_text(TST, encoding="utf-8")
    elif operation == "publish-pr":
        require(Path(values[0]).read_text(), "approved summary must be consumable")
        Path(values[1]).write_text('{"number":1,"base":"fixture-trunk"}\n')
    elif operation == "cleanup":
        event["step"] = values[0]
        if len(values) == 2:
            event["pr"] = read_json(Path(values[1]))
    else:
        raise ValueError(f"unknown fixture operation: {operation}")
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return 23 if operation == "model" and values[0] == "true" else 0


def shell_action(operation: str, args: list[Any]) -> dict[str, Any]:
    """Build a real shell/exec request targeting the contained synthetic helper."""
    return {
        "uses": "process:shell/exec",
        "with": {
            "command": "python3",
            "args": ["source://runtime_fixture.py", "--synthetic", operation, *args],
        },
    }


class Fixture:
    """Own one fresh home, copied graph and its detached runtime runners."""

    def __init__(self, binary: Path, plugin: Path, base: Path, case: str) -> None:
        self.root = base / case
        self.root.mkdir()
        self.workspace = self.root / "workspace"
        self.source = self.root / "source"
        self.home = self.root / "home"
        self.binary = binary
        self.case = case
        self.max_iters = 0
        self.sequence = 0
        self.pids: set[int] = set()
        for directory in (
            self.workspace,
            self.source,
            self.root / "user",
            self.root / "temp",
        ):
            directory.mkdir()
        user = self.root / "user"
        self.env = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(user),
            "USERPROFILE": str(user),
            "XDG_CONFIG_HOME": str(user / "config"),
            "XDG_CACHE_HOME": str(user / "cache"),
            "XDG_DATA_HOME": str(user / "data"),
            "TMPDIR": str(self.root / "temp"),
            "LANG": "en_US.UTF-8",
            "NO_COLOR": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
        # No commits or refs are created; the actual guard needs a Git root.
        subprocess.run(
            ["git", "init", "--quiet", str(self.workspace)],
            env=self.env,
            check=True,
            capture_output=True,
            timeout=15,
        )
        self.cli("home", "init", "--mode", "standalone")
        self.cli("plugins", "install", "--path", str(plugin / "plugin.yaml"))
        import yaml

        manifest = yaml.safe_load((plugin / "plugin.yaml").read_text())
        payload = {}
        for name in ("plugin.yaml", *manifest["package"]["files"]):
            source = plugin / name
            installed = self.home / "plugins/shell/0.1.0" / name
            require(
                source.read_bytes() == installed.read_bytes(), "shell payload drift"
            )
            payload[name] = digest(source)
        write_json(self.root / "shell-payload.json", payload)

    def cli(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        """Run the actual CLI with isolated environment and retain full receipts."""
        result = subprocess.run(
            [
                str(self.binary),
                "--home",
                str(self.home),
                *args,
                "--format",
                "json",
                "--ui",
                "plain",
            ],
            cwd=self.workspace,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.sequence += 1
        try:
            output = json.loads(result.stdout)
        except ValueError:
            output = result.stdout
        if isinstance(output, dict) and isinstance(output.get("runner_pid"), int):
            self.pids.add(output["runner_pid"])
        receipt = self.root / f"command-{self.sequence:03}.json"
        write_json(
            receipt,
            {
                "args": args,
                "exit": result.returncode,
                "stdout": output,
                "stderr": result.stderr,
            },
        )
        require(not ok or result.returncode == 0, f"CLI failed; inspect {receipt}")
        return result

    def running(self) -> bool:
        """Check owned runner PIDs, treating exited zombies as settled."""
        if not self.pids:
            return False
        result = subprocess.run(
            [
                "/bin/ps",
                "-p",
                ",".join(map(str, sorted(self.pids))),
                "-o",
                "pid=,stat=,command=",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return any(
            len(fields) == 3 and "Z" not in fields[1] and str(self.home) in fields[2]
            for fields in (
                line.split(maxsplit=2) for line in result.stdout.splitlines()
            )
        )

    def wait(self) -> dict[str, Any]:
        """Wait for durable root settlement AND runner exit before the next gate."""
        deadline = time.monotonic() + 90
        path = self.home / "runs/run_regression/state.json"
        while time.monotonic() < deadline:
            if path.exists():
                state = read_json(path)
                if state["status"] in TERMINAL | {"blocked"} and not self.running():
                    return json.loads(self.cli("runs", "show", "regression").stdout)
            time.sleep(0.1)
        raise AssertionError(f"run did not settle: {self.root}")

    def close(self) -> None:
        """Cancel incomplete fixture work through the CLI and require runner exit."""
        path = self.home / "runs/run_regression/state.json"
        if path.exists() and read_json(path)["status"] not in TERMINAL:
            if read_json(path)["status"] == "blocked":
                self.decide("reject")
            else:
                self.cli("runs", "cancel", "regression")
            require(
                self.wait()["status"] in TERMINAL, "fixture cancellation incomplete"
            )
        deadline = time.monotonic() + 30
        while self.running() and time.monotonic() < deadline:
            time.sleep(0.1)
        require(not self.running(), "owned runtime runner did not exit")
        write_json(
            self.root / "settled-runners.json",
            {"pids": sorted(self.pids), "all_exited": True},
        )

    def events(self, operation: str) -> list[dict[str, Any]]:
        """Return real sandbox observations for one synthetic action type."""
        path = self.workspace / "events.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines()]
        return [record for record in records if record["operation"] == operation]

    def heads(self) -> dict[str, Any]:
        """Read published root-shared document revisions, without editing state."""
        return read_json(self.home / "runs/run_regression/documents/heads.json")

    def observation(self) -> dict[str, Any]:
        """Retain concise actual state even when an assertion fails mid-scenario."""
        states = []
        for path in (self.home / "runs/run_regression").rglob("state.json"):
            state = read_json(path)
            states.append(
                {
                    "run_id": state["run_id"],
                    "status": state["status"],
                    "steps": {
                        name: {
                            "status": step["status"],
                            "executions": step["executions"],
                            "output": (step.get("last_result") or {}).get("output"),
                        }
                        for name, step in state["steps"].items()
                    },
                }
            )
        return {
            "states": states,
            "models": len(self.events("model")),
            "scans": len(self.events("scan")),
            "cleanup": self.events("cleanup"),
            "document_heads": self.heads(),
        }

    def blob(self, document: str) -> bytes:
        """Read immutable bytes at the document's current published revision."""
        revision = self.heads()[document]
        return (
            self.home
            / "runs/run_regression/documents/blobs"
            / revision["blob"]["sha256"]
        ).read_bytes()

    def gate(self) -> dict[str, Any]:
        """Require exactly one active nested gate with the three real revisions."""
        requests = []
        for path in (self.home / "runs/run_regression").rglob("state.json"):
            for step in read_json(path)["steps"].values():
                if step["status"] == "blocked":
                    request = (
                        (step.get("last_result") or {})
                        .get("output", {})
                        .get("review_request")
                    )
                    if request:
                        requests.append(request)
        require(len(requests) == 1, f"expected one nested review, got {len(requests)}")
        request = requests[0]
        require(request["step_id"] == "review_implementation", "wrong review gate")
        require(
            {item["document"] for item in request["review_documents"]}
            == {"implementation_notes", "change_summary_title", "pr_body"},
            "review did not bind all three documents",
        )
        for revision in request["review_documents"]:
            require(
                revision == self.heads()[revision["document"]],
                "gate reviewed stale revision",
            )
        return request

    def decide(self, decision: str) -> dict[str, Any]:
        """Record a synthetic fixture-only decision using the public root CLI."""
        self.cli(
            "runs",
            "gate",
            decision,
            "regression",
            "implementation-review",
            "--actor",
            "synthetic-regression",
            "--reason",
            REASON,
        )
        return self.wait()

    def install(
        self,
        original: dict[str, Any],
        iteration: dict[str, Any],
        loop: dict[str, Any],
        example: Path,
    ) -> None:
        """Copy actual modules; substitute only deterministic external participants."""
        import yaml

        modules = self.source / "modules"
        (modules / "scripts").mkdir(parents=True)
        helper = Path(__file__)
        for directory in (self.source, modules):
            shutil.copyfile(helper, directory / "runtime_fixture.py")
        for name in (
            "check_working_files.py",
            "reviewer_context.py",
            "reviewed_copy.py",
            "require_implementation_approval.py",
        ):
            shutil.copyfile(
                example / "modules/scripts" / name, modules / "scripts" / name
            )
        iteration = copy.deepcopy(iteration)
        # The removed profile is provider-only; all controls and bindings survive.
        iteration.pop("profiles", None)
        for step in iteration["steps"]:
            if step["id"] in {"implement_fix", "implement_plan"}:
                model_id = step["id"]
                data = step["with"]
                context_names = [
                    binding["$document"] for binding in data["context_files"]
                ]
                replacement = shell_action(
                    "model",
                    [
                        str(self.case == "early-failure").lower(),
                        str(len(context_names)),
                        str(context_names.index("tst_comments")),
                        *data["context_files"],
                        data["response_file"],
                        data["summary_title_file"],
                        data["pr_body_file"],
                    ],
                )
                step.clear()
                step.update(id=model_id, **replacement)
            elif step["id"] == "scan_tst_comments":
                output = step["with"]["output_file"]
                step.clear()
                step.update(id="scan_tst_comments", **shell_action("scan", [output]))
        (modules / "implementation_iteration.module.yaml").write_text(
            yaml.safe_dump(iteration, sort_keys=False)
        )
        (modules / "implementation.module.yaml").write_text(
            yaml.safe_dump(loop, sort_keys=False)
        )
        loop_step = next(
            step for step in loop["steps"] if step["id"] == "implementation_loop"
        )
        self.max_iters = loop_step["loop"]["max_iters"]
        require(1 <= self.max_iters <= 5, "authored iteration cap must be at most five")
        initialize = copy.deepcopy(original["steps"][0])
        require(initialize["id"] == "initialize_reviewer_context", "root init moved")
        documents = copy.deepcopy(original["documents"])
        seed = {
            "id": "seed",
            **shell_action(
                "seed",
                [
                    {"$document": name, "access": "write"}
                    for name in context_names
                    if name != "reviewer_context" and "initial" not in documents[name]
                ],
            ),
        }
        implementation = next(
            copy.deepcopy(step)
            for step in original["steps"]
            if step["id"] == "implementation_loop"
        )
        implementation_ref = implementation["module"]["ref"]
        commit = next(
            step for step in original["steps"] if step["id"] == "commit_implementation"
        )
        cleanup = copy.deepcopy(original["cleanup"])
        for step in cleanup:
            args = [step["id"]]
            if step["id"] == "sync_trunk_branch":
                args.append(step["with"]["pr_file"])
            replacement = shell_action("cleanup", args)
            step.pop("uses")
            step.pop("with")
            step.update(replacement)
        flow = {
            "schema": original["schema"],
            "id": "hotfix_runtime_regression",
            "version": original["version"],
            "plugins": {"shell": "0.1.0"},
            "modules": {implementation_ref: original["modules"][implementation_ref]},
            "network": {"mode": "none"},
            "workspace": original["workspace"],
            "inputs": original["inputs"],
            "documents": documents,
            "steps": [
                initialize,
                seed,
                implementation,
                {
                    "id": "publish_pr",
                    **shell_action(
                        "publish-pr",
                        [
                            commit["with"]["summary_file"],
                            {"$document": "pr", "access": "write"},
                        ],
                    ),
                },
                {"id": "finish", "control": "control.finish"},
            ],
            "cleanup": cleanup,
        }
        path = self.source / "workflow.yaml"
        path.write_text(yaml.safe_dump(flow, sort_keys=False))
        inputs = self.root / "inputs.json"
        write_json(
            inputs, {"repo_path": str(self.workspace), "jira_ticket_id": "PROJ-123"}
        )
        self.cli("workflows", "check", "--path", str(path))
        self.cli(
            "workflows", "check", "--path", str(path), "--inputs-file", str(inputs)
        )
        self.cli(
            "workflows", "explain", "--path", str(path), "--inputs-file", str(inputs)
        )
        self.cli("workflows", "install", "--path", str(path), "--approve")
        readiness = json.loads(
            self.cli(
                "workflows",
                "check",
                "hotfix_runtime_regression@0.1.0",
                "--inputs-file",
                str(inputs),
                "--live",
            ).stdout
        )
        require(readiness["status"] == "ready", "fixture not ready")
        self.cli(
            "workflows",
            "run",
            "hotfix_runtime_regression@0.1.0",
            "--run-ref",
            "regression",
            "--inputs-file",
            str(inputs),
            "--local-only",
        )


def check_case(fixture: Fixture) -> dict[str, Any]:
    """Exercise real gate/loop semantics and verify documents, context and cleanup."""
    state = fixture.wait()
    case = fixture.case
    if case != "early-failure":
        require(state["status"] == "blocked", "first pass did not reach review")
        first = fixture.gate()
        models = fixture.events("model")
        require(
            len(models) == 1 and models[0]["tst"] == "",
            "first model did not receive initial empty TST",
        )
        require(
            len(models[0]["ledger"]) == 1, "first model inherited unexpected feedback"
        )
        require(not fixture.events("scan"), "scanner ran before first decision")
        require(
            not APPROVED_IMPLEMENTATION.intersection(fixture.heads()),
            "export ran before approval",
        )
        write_json(fixture.root / "first-review.json", first)
        if case in {"request-changes", "iteration-limit"}:
            previous = first
            count = 1 if case == "request-changes" else fixture.max_iters
            for number in range(1, count + 1):
                state = fixture.decide("request-changes")
                require(
                    len(fixture.events("scan")) == number,
                    "changes did not scan exactly once",
                )
                require(
                    not APPROVED_IMPLEMENTATION.intersection(fixture.heads()),
                    "request-changes exported unapproved bytes",
                )
                if case == "iteration-limit" and state["status"] != "blocked":
                    break
                require(
                    state["status"] == "blocked",
                    f"loop exited after {number} changes, before iteration "
                    f"{number + 1}; root status={state['status']}",
                )
                current = fixture.gate()
                require(
                    current["run_id"] != previous["run_id"],
                    "iteration reused child identity",
                )
                models = fixture.events("model")
                require(
                    len(models) <= fixture.max_iters,
                    "fresh iteration exceeded authored max_iters",
                )
                require(len(models) == number + 1, "unexpected model iteration count")
                latest = models[-1]
                require(
                    latest["tst"] == TST, "fresh iteration lost published TST context"
                )
                require(
                    latest["prior_notes"]
                    == "".join(f"Implementation {n}\n" for n in range(1, number + 1)),
                    "fresh iteration lost published notes",
                )
                ledger = latest["ledger"]
                require(
                    ledger[0]["root_run_id"] == "regression",
                    "child replaced root ledger identity",
                )
                require(
                    len(ledger) == number + 1,
                    "fresh iteration lost prior ledger decisions",
                )
                decision = ledger[-1]
                require(
                    decision["decision"] == "request_changes"
                    and decision["reason"] == REASON
                    and decision["run_id"] == previous["run_id"]
                    and decision["review_request"] == previous,
                    "ledger lost exact bound feedback",
                )
                write_json(fixture.root / f"review-{number + 1}.json", current)
                previous = current
        if case == "reject":
            state = fixture.decide("reject")
        elif case != "iteration-limit":
            reviewed = fixture.gate()
            state = fixture.decide("approve")
            write_json(fixture.root / "approved-review.json", reviewed)
    expected_success = case in {"approve", "request-changes"}
    if expected_success:
        require(state["status"] == "success", "approval did not complete")
        for source, target in (
            ("implementation_notes", "approved_notes"),
            ("change_summary_title", "approved_summary"),
            ("pr_body", "approved_pr_body"),
        ):
            require(
                fixture.blob(source) == fixture.blob(target),
                f"export changed exact reviewed bytes: {target}",
            )
            require(
                fixture.heads()[source] in reviewed["review_documents"],
                "export source was not exact-reviewed",
            )
        ledger = [
            json.loads(line) for line in fixture.blob("reviewer_context").splitlines()
        ]
        require(
            ledger[-1]["decision"] == "approved"
            and ledger[-1]["review_request"] == reviewed,
            "approval not captured exactly",
        )
    else:
        require(
            state["status"] in {"failed", "canceled"},
            "negative scenario unexpectedly completed",
        )
        require("pr" not in fixture.heads(), "negative scenario published PR")
        require(
            not APPROVED_IMPLEMENTATION.intersection(fixture.heads()),
            "negative scenario exported implementation",
        )
        if case == "early-failure":
            require(
                state["status"] == "failed", "injected producer failure was not failed"
            )
            require(
                "change_summary_title" not in fixture.heads(),
                "failed producer published output",
            )
            require(
                fixture.blob("implementation_notes") == b"",
                "failed producer replaced the initial notes revision",
            )
        if case == "iteration-limit":
            require(state["status"] == "failed", "iteration limit was not failed")
            implementation = state["steps"]["implementation_loop"]
            require(
                implementation["status"] == "failed",
                "implementation module returned success without approval",
            )
            child_id = implementation["last_result"]["output"]["child_run_id"]
            children = [
                read_json(path)
                for path in (fixture.home / "runs/run_regression").rglob("state.json")
            ]
            child = next(item for item in children if item["run_id"] == child_id)
            require(
                child["status"] == "failed", "contained implementation did not fail"
            )
            guard = child["steps"]["require_implementation_approval"]
            require(
                guard["status"] == "failed" and guard["executions"] == 1,
                "authored approval guard did not fail exactly once",
            )
            require(
                guard["last_result"]["stderr"].strip(),
                "approval guard failed without an explanatory message",
            )
            require(
                state["steps"]["publish_pr"]["status"] == "skipped"
                and state["steps"]["publish_pr"]["executions"] == 0,
                "exhaustion reached the outer document consumer",
            )
            write_json(fixture.root / "exhaustion-guard.json", guard)
    scans = len(fixture.events("scan"))
    expected_scans = (
        len(fixture.events("model"))
        if case == "iteration-limit"
        else (1 if case == "request-changes" else 0)
    )
    require(scans == expected_scans, "scanner ran on approval/rejection/failure")
    models = fixture.events("model")
    if case == "iteration-limit":
        require(1 <= len(models) <= fixture.max_iters, "loop exceeded authored cap")
    else:
        require(
            len(models) == (2 if case == "request-changes" else 1),
            "unexpected model visit count",
        )
    require(
        len({model["run_id"] for model in models}) == len(models),
        "model invocations reused child scope",
    )
    cleanup = [event["step"] for event in fixture.events("cleanup")]
    expected_cleanup = (
        ["sync_trunk_branch", "checkout_trunk_branch", "delete_local_feature_branch"]
        if expected_success
        else (
            ["checkout_trunk_branch", "delete_local_feature_branch"]
            if state["status"] == "failed"
            else []
        )
    )
    require(cleanup == expected_cleanup, f"wrong terminal cleanup: {cleanup}")
    write_json(fixture.root / "final-state.json", state)
    write_json(fixture.root / "document-heads.json", fixture.heads())
    return {
        "case": case,
        "status": "passed",
        "runtime_status": state["status"],
        "models": len(models),
        "scans": scans,
        "max_iters": fixture.max_iters,
        "cleanup": cleanup,
        "evidence": str(fixture.root),
    }


def main() -> int:
    """Run every required regression with explicit runtime and fixture paths."""
    if len(sys.argv) > 1 and sys.argv[1] == "--synthetic":
        return synthetic(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", required=True, type=Path)
    parser.add_argument("--shell-plugin", required=True, type=Path)
    parser.add_argument("--fixture-base", required=True, type=Path)
    parser.add_argument(
        "--example",
        choices=("hotfix_ticket_delivery", "cursor_ticket_delivery"),
        default="hotfix_ticket_delivery",
    )
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    import yaml

    repository = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repository / "scripts"))
    from check_examples import VERSION, approved_home_base

    example = repository / "examples" / args.example
    cases = list(dict.fromkeys(args.case or CASES))
    base = approved_home_base(str(args.fixture_base))
    binary = args.transist.resolve(strict=True)
    plugin = args.shell_plugin.resolve(strict=True)
    root = Path(tempfile.mkdtemp(prefix="hotfix-runtime-", dir=base))
    print(f"EVIDENCE {root}", flush=True)
    approval_helper = example / "modules/scripts/require_implementation_approval.py"
    loop_source = yaml.safe_load(
        (example / "modules/implementation.module.yaml").read_text()
    )
    require(
        approval_helper.is_file()
        and any(
            step["id"] == "require_implementation_approval"
            for step in loop_source["steps"]
        ),
        "authored approval helper/step missing",
    )
    sources = [
        example / "workflow.yaml",
        example / "modules/implementation.module.yaml",
        example / "modules/implementation_iteration.module.yaml",
        *[
            example / "modules/scripts" / name
            for name in (
                "reviewer_context.py",
                "reviewed_copy.py",
                "check_working_files.py",
                "require_implementation_approval.py",
            )
        ],
    ]
    original, loop, iteration = [
        yaml.safe_load(path.read_text()) for path in sources[:3]
    ]
    versions = subprocess.run(
        [str(binary), "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    require(
        versions.stdout.strip() == f"transist {VERSION}", f"requires transist {VERSION}"
    )
    write_json(
        root / "identities.json",
        {
            "runtime": str(binary),
            "runtime_sha256": digest(binary),
            "version": versions.stdout.strip(),
            "runner_sha256": digest(Path(__file__)),
            "sources": {
                str(path.relative_to(repository)): digest(path) for path in sources
            },
        },
    )
    results = []
    for case in cases:
        fixture = None
        try:
            fixture = Fixture(binary, plugin, root, case)
            fixture.install(original, iteration, loop, example)
            result = check_case(fixture)
        except Exception:
            result = {
                "case": case,
                "status": "failed",
                "traceback": traceback.format_exc(),
            }
        finally:
            if fixture is not None:
                try:
                    try:
                        if (fixture.home / "runs/run_regression/state.json").exists():
                            write_json(
                                fixture.root / "observed.json", fixture.observation()
                            )
                    finally:
                        fixture.close()
                except Exception:
                    result = {
                        "case": case,
                        "status": "failed",
                        "cleanup_traceback": traceback.format_exc(),
                        "prior_result": result,
                    }
        results.append(result)
        write_json(root / "summary.json", results)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    passed = sum(result["status"] == "passed" for result in results)
    print(f"RESULT {passed}/{len(cases)} passed; {root / 'summary.json'}", flush=True)
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
