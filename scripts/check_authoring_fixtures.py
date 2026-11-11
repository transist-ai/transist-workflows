#!/usr/bin/env python3
"""Compile, explain and execute the finite conversational-authoring fixture inventory.

Only external model/gh peers are fake. Installed packages, schemas, compiler,
document storage, sandbox, gates and detached runtime runners are real.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import hashlib
import http.server
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
from typing import Iterator

import yaml

from check_examples import CheckError, ROOT, inspect_graph, load_yaml
from check_installed_examples import executable, fixture_python, local_network, require
from installed_delivery import DeliveryDriver
from source_identity import source_identity

FIXTURES = ROOT / "tests/fixtures/conversational_authoring"
INVENTORY = (
    "diagnostic_advisory",
    "approved_draft_publication",
    "two_approval_revision",
)
SCENARIOS = {
    "diagnostic_advisory": ("approved", "rejected", "changed"),
    "approved_draft_publication": ("approved", "rejected", "changed"),
    "two_approval_revision": ("approved", "reject_first", "reject_second", "changed"),
}
TEXT = "  fictional café\r\nsecond line ☃\n\n"
ANSWER = "## Fictional draft\n\nBounded advice; no machine action. café\n"
FAKE_GH = r"""
import json, sys, urllib.request
args = sys.argv[1:]
if args == ["--version"]:
    print("gh version fixture")
    raise SystemExit(0)
assert args[:2] == ["pr", "create"], args
assert "--draft" in args and "--fill" not in args
request = urllib.request.Request(ENDPOINT + "/publish",
    data=json.dumps({"args": args}).encode(),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=10) as response:
    assert response.status == 200
print("https://example.invalid/fixture/drafts/pull/1")
"""


def select(names: list[str]) -> list[str]:
    """Select once in canonical order; unknown names or missing roots fail closed."""
    require(not set(names) - set(INVENTORY), "unknown authoring fixture")
    require(
        {path.name for path in FIXTURES.iterdir() if path.is_dir()} == set(INVENTORY),
        "authoring fixture inventory drift",
    )
    return [name for name in INVENTORY if not names or name in names]


def revision_contract() -> None:
    """Require exactly a second authored gate and its protected read, no other drift."""
    base = load_yaml(FIXTURES / "approved_draft_publication/workflow.yaml")
    revised = load_yaml(FIXTURES / "two_approval_revision/workflow.yaml")
    second = revised["steps"].pop(-2)
    require(
        second["id"] == "review_publication"
        and second["control"] == "control.gate.manual"
        and second["with"]["review_documents"] == ["draft"],
        "revision must add a distinct document-review gate",
    )
    read = revised["steps"][-1]["with"]["body_file"]
    require(read["reviewed_by"] == "review_publication", "second read is unprotected")
    read["reviewed_by"] = "review_draft"
    require(base == revised, "revision changed more than its intended gate/read")
    require(
        (FIXTURES / "approved_draft_publication/inputs.example.yaml").read_bytes()
        == (FIXTURES / "two_approval_revision/inputs.example.yaml").read_bytes(),
        "revision changed sample bindings",
    )


class Peer(http.server.BaseHTTPRequestHandler):
    """Record model wire requests and fake gh publication attempts separately."""

    def do_POST(self) -> None:
        """Serve only declared local fake endpoints with deterministic responses."""
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        require(self.path in {"/v1/chat/completions", "/publish"}, "unexpected peer")
        self.server.events.append({"path": self.path, "body": body})
        response = (
            {"ok": True}
            if self.path == "/publish"
            else {
                "choices": [{"message": {"role": "assistant", "content": ANSWER}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }
        )
        raw = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args: object) -> None:
        """Payloads belong only in the retained explicit observation receipt."""


@contextmanager
def peer() -> Iterator[http.server.ThreadingHTTPServer]:
    """Own an exact loopback listener and join its threads without skips."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Peer)
    server.events = []
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
        require(not thread.is_alive(), "authoring peer did not settle")


def digest_tree(root: Path) -> dict[str, str]:
    """Fingerprint existing regular bytes to detect static CLI home writes."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def provenance(driver: DeliveryDriver) -> None:
    """Retain source heads/diffs and actual binary/fixture hashes for later review."""
    sources = {
        label: source_identity(root)
        for label, root in (("workflows", ROOT), ("plugins", driver.plugins))
    }
    (driver.root / "provenance.json").write_text(
        json.dumps(
            {
                "sources": sources,
                "platform": platform.platform(),
                "python": sys.version,
                "binary_sha256": hashlib.sha256(driver.binary.read_bytes()).hexdigest(),
                "fixture_files": digest_tree(FIXTURES),
                "runner_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
            },
            indent=2,
        )
    )


def source_receipts(driver: DeliveryDriver, path: Path, inputs: dict) -> None:
    """Validate/explain real source before installation, readiness or dispatch."""
    before = digest_tree(driver.home)
    bindings = driver.root / "authoring-bindings.json"
    bindings.write_text(json.dumps(inputs))
    driver.cli("workflows", "check", "--path", str(path))
    checked = json.loads(
        driver.cli(
            "workflows", "check", "--path", str(path), "--inputs-file", str(bindings)
        ).stdout
    )
    require(
        all(
            c["status"] in {"passed", "deferred_to_dispatch"}
            or (
                c["status"] == "not_evaluated"
                and c["code"] in {"secret_value", "external_state"}
            )
            for c in checked["checks"]
        ),
        "source validation has unresolved static/authority failures",
    )
    require(
        any(c["status"] == "deferred_to_dispatch" for c in checked["checks"]),
        "managed payload checks must remain deferred",
    )
    unbound = json.loads(driver.cli("workflows", "explain", "--path", str(path)).stdout)
    require(
        unbound["scopes"]["root"]["inputs"]["workspace_path"]["state"] == "missing"
        and unbound["scopes"]["root"]["inputs"]["model"]["state"] == "missing",
        "unresolved required bindings not explicit before start",
    )
    args = ("workflows", "explain", "--path", str(path), "--inputs-file", str(bindings))
    reports = [driver.cli(*args).stdout for _ in range(2)]
    require(reports[0] == reports[1], "explanation is not deterministic")
    report = json.loads(reports[0])
    require(
        all(
            pin["status"] == "resolved" and pin["sha256"]
            for pin in report["pins"].values()
        ),
        "installed exact contract pins must resolve",
    )
    (driver.root / "source-check.json").write_text(json.dumps(checked, indent=2))
    (driver.root / "explanation-unbound.json").write_text(json.dumps(unbound, indent=2))
    (driver.root / "explanation-bound.json").write_text(reports[0])
    if path.parent.name == "two_approval_revision":
        previous = FIXTURES / "approved_draft_publication/workflow.yaml"
        compared = json.loads(driver.cli(*args, "--compare-to", str(previous)).stdout)
        (driver.root / "comparison.json").write_text(json.dumps(compared, indent=2))
        changes = compared["comparison"]["changes"]
        require(changes, "revision explanation omitted changes")
        require(
            not any(c["category"] in {"pins", "limits", "actions"} for c in changes),
            "revision changed contracts/actions/limits",
        )
        expected = json.loads((FIXTURES / "revision-diff-paths.json").read_text())
        require([c["path"] for c in changes] == expected, "unexpected explanation diff")
    require(digest_tree(driver.home) == before, "source validation/explain wrote home")
    require(not driver.runs, "authoring created a run")


def gate(state: dict, step: str, document: str) -> dict:
    """Require the exact current document revision in a genuine blocked request."""
    require(state["status"] == "blocked", "fixture did not wait at authored gate")
    current = state["steps"][step]
    require(current["status"] == "blocked", "wrong gate blocked")
    request = current["last_result"]["output"]["review_request"]
    require(request["step_id"] == step, "wrong lexical review scope")
    require(
        len(request["review_documents"]) == 1
        and request["review_documents"][0]["document"] == document,
        "wrong document review",
    )
    return request["review_documents"][0]


def decide(driver: DeliveryDriver, name: str, gate_id: str, decision: str) -> dict:
    """Record only an explicitly authorized synthetic fixture decision via CLI."""
    driver.cli(
        "runs",
        "gate",
        decision,
        name,
        gate_id,
        "--actor",
        "synthetic-fixture-reviewer",
        "--reason",
        "fake-test-only decision",
    )
    return driver.wait(name)


def relocated(flow: dict, port: int) -> dict:
    """Bind the one fake port identically for both revisions, preserving all else."""
    flow = copy.deepcopy(flow)
    if flow["network"]["mode"] != "none":
        flow["network"] = local_network(port)
    for step in flow["steps"]:
        if step.get("network", {}).get("mode") == "loopback":
            step["network"] = local_network(port)
        data = step.get("with", {})
        for field in ("base_url", "destination"):
            if field in data:
                data[field] = f"http://127.0.0.1:{port}/v1"
    return flow


def run_fixture(binary: Path, plugins: Path, base: Path, fixture: str) -> None:
    """Run every required real-runtime scenario for one synthetic authored flow."""
    path = FIXTURES / fixture / "workflow.yaml"
    flow, _, _ = inspect_graph(path)
    driver = DeliveryDriver(binary, plugins, base, "authoring-" + fixture)
    observations = []
    try:
        provenance(driver)
        unresolved = json.loads(
            driver.cli("workflows", "explain", "--path", str(path)).stdout
        )
        require(
            all(
                pin["status"] == "unresolved_missing"
                for pin in unresolved["pins"].values()
            ),
            "missing installed contracts were not explicit",
        )
        driver.install_plugins(path)
        inputs = load_yaml(path.parent / "inputs.example.yaml")
        inputs["workspace_path"] = str(driver.workspace)
        source_receipts(driver, path, inputs)
        with peer() as server, driver.peers([server]):
            fake = driver.root / "bin"
            fake.mkdir(exist_ok=True)
            gh = fake / "gh"
            endpoint = f"http://127.0.0.1:{server.server_port}"
            gh.write_text(f"#!{fixture_python()}\nENDPOINT = {endpoint!r}\n" + FAKE_GH)
            gh.chmod(0o755)
            driver.env["PATH"] = str(fake) + os.pathsep + driver.env["PATH"]
            config = driver.home / "config.yaml"
            settings = load_yaml(config)
            settings["policy"]["child_env"] = {"inherit": False, "allowlist": ["PATH"]}
            config.write_text(yaml.safe_dump(settings))
            bound = relocated(flow, server.server_port)
            reference = driver.install_flow(bound, fixture + "_test")
            for scenario in SCENARIOS[fixture]:
                selected = reference
                advisory = fixture == "diagnostic_advisory"
                two = fixture == "two_approval_revision"
                document = "diagnostic" if advisory else "draft"
                consumer = "advise" if advisory else "publish"
                if scenario == "changed":
                    changed = copy.deepcopy(bound)
                    writer = copy.deepcopy(changed["steps"][0])
                    writer["id"] = "new_revision_after_review"
                    writer["with"]["path"] = "replacement.txt"
                    writer["with"]["output_file"]["$document"] = document
                    changed["steps"].insert(-1, writer)
                    selected = driver.install_flow(changed, fixture + "_changed")
                    (driver.workspace / "replacement.txt").write_text("replacement\n")
                (driver.workspace / inputs["source_path"]).write_bytes(TEXT.encode())
                name = fixture + "_" + scenario
                first = len(server.events)
                state = driver.start(selected, name, inputs)
                reviewed = gate(
                    state, "review_diagnostic" if advisory else "review_draft", document
                )
                expected_bytes = TEXT.encode() if advisory else ANSWER.encode()
                require(
                    driver.blob(name, reviewed) == expected_bytes, "review bytes differ"
                )
                require(
                    state["steps"][consumer]["executions"] == 0, "early consumption"
                )
                require(
                    len(server.events) - first == (0 if advisory else 1),
                    "effect occurred before first approval",
                )
                checkpoints = [
                    {
                        "waiting_at": (
                            "review_diagnostic" if advisory else "review_draft"
                        ),
                        "consumer_attempts": state["steps"][consumer]["executions"],
                        "publication_calls": 0,
                        "reviewed": reviewed,
                    }
                ]
                (driver.workspace / inputs["source_path"]).write_text(
                    "later workspace bytes"
                )
                reject_first = scenario in {"rejected", "reject_first"}
                state = decide(
                    driver,
                    name,
                    "diagnostic-transfer" if advisory else "draft-review",
                    "reject" if reject_first else "approve",
                )
                if two and not reject_first:
                    second = gate(state, "review_publication", "draft")
                    require(
                        second == reviewed, "second gate reviewed a different revision"
                    )
                    require(
                        state["steps"]["publish"]["executions"] == 0
                        and len(server.events) - first == 1,
                        "first approval alone permitted publication",
                    )
                    checkpoints.append(
                        {
                            "waiting_at": "review_publication",
                            "first_approval_recorded": True,
                            "consumer_attempts": state["steps"]["publish"][
                                "executions"
                            ],
                            "publication_calls": 0,
                            "reviewed": second,
                        }
                    )
                    state = decide(
                        driver,
                        name,
                        "publication-review",
                        "reject" if scenario == "reject_second" else "approve",
                    )
                events = server.events[first:]
                model = [e for e in events if e["path"] == "/v1/chat/completions"]
                publication = [e for e in events if e["path"] == "/publish"]
                success = scenario == "approved"
                require(
                    state["status"] == ("success" if success else "failed"),
                    "wrong outcome",
                )
                require(
                    len(model) == (int(success) if advisory else 1), "wrong model count"
                )
                require(
                    len(publication) == (int(success) if not advisory else 0),
                    "wrong publication count",
                )
                if model:
                    require(
                        model[0]["body"]["messages"][1]["content"] == TEXT,
                        "provider bytes drift",
                    )
                    model_step = next(
                        s
                        for s in bound["steps"]
                        if s.get("uses") == "process:openai.compatible/chat_complete"
                    )
                    require(
                        model[0]["body"]["messages"][0]["content"]
                        == model_step["with"]["system_prompt"],
                        "system prompt drift",
                    )
                if publication:
                    args = publication[0]["body"]["args"]
                    require(
                        args[args.index("--body") + 1] == ANSWER,
                        "published unreviewed bytes",
                    )
                    require(
                        args[args.index("-R") + 1] == inputs["repository"],
                        "wrong repository",
                    )
                    require(
                        args[args.index("--title") + 1] == inputs["title"],
                        "wrong title",
                    )
                    for field in ("head", "base"):
                        require(
                            args[args.index("--" + field) + 1] == inputs[field],
                            "wrong publication branch",
                        )
                if scenario == "changed":
                    require(
                        driver.head(name, document)["revision_id"]
                        != reviewed["revision_id"],
                        "no actual new revision",
                    )
                    require(
                        "not covered" in json.dumps(state["steps"][consumer]),
                        "not revision enforcement",
                    )
                if success and advisory:
                    require(
                        driver.blob(name, driver.head(name, "response"))
                        == ANSWER.encode(),
                        "missing managed answer",
                    )
                require(
                    state["steps"][consumer]["executions"]
                    == int(success or scenario == "changed"),
                    "unexpected consumer attempt count",
                )
                require(
                    sorted(p.name for p in driver.workspace.iterdir())
                    == sorted(
                        [inputs["source_path"]]
                        + (
                            ["replacement.txt"]
                            if scenario == "changed"
                            or (driver.workspace / "replacement.txt").exists()
                            else []
                        )
                    ),
                    "operational files escaped into workspace",
                )
                observations.append(
                    {
                        "scenario": scenario,
                        "run": name,
                        "status": state["status"],
                        "reviewed": reviewed,
                        "model_calls": len(model),
                        "publication_calls": len(publication),
                        "approval_checkpoints": checkpoints,
                        "events": events,
                    }
                )
                print(
                    f"PASS {fixture} {scenario}; models={len(model)} "
                    f"publications={len(publication)}",
                    flush=True,
                )
        driver.settle()
        (driver.root / "receipt.json").write_text(
            json.dumps(
                {
                    "complete": True,
                    "fixture": fixture,
                    "scenarios": observations,
                    "source_files": digest_tree(path.parent),
                    "owned_runners": sorted(driver.pids),
                    "runners_exited": not driver.running(),
                    "listener_settled": True,
                },
                indent=2,
            )
        )
    finally:
        driver.close()
        driver.settle()


def run_all(
    binary: Path, plugins: Path, base: Path, names: list[str] | None = None
) -> None:
    """Require the canonical inventory, also called by Step 12's unfiltered runner."""
    revision_contract()
    selected = select(names or [])
    for fixture in selected:
        run_fixture(binary, plugins, base, fixture)
    print(f"RESULT {len(selected)} authoring fixtures passed; zero skips", flush=True)


def main(argv: list[str] | None = None) -> int:
    """Run selected fixtures with explicit matching binaries and retained storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", required=True, type=Path)
    parser.add_argument("--admin-bin", required=True, type=Path)
    parser.add_argument("--plugins-dir", required=True, type=Path)
    parser.add_argument("--fixture-base", required=True, type=Path)
    parser.add_argument("--fixture", action="append", choices=INVENTORY, default=[])
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(
            __debug__ and not os.environ.get("PYTHONOPTIMIZE"), "assertions required"
        )
        binary = executable(args.transist, "transist")
        executable(args.admin_bin, "transist-admin")
        require(
            args.plugins_dir.is_absolute() and args.plugins_dir.is_dir(),
            "plugins-dir missing",
        )
        require(
            args.fixture_base.is_absolute()
            and args.fixture_base.is_dir()
            and not args.fixture_base.is_symlink(),
            "fixture-base must exist and be nonsymlink",
        )
        if args.list:
            for name in select(args.fixture):
                print(f"{name}: {', '.join(SCENARIOS[name])}")
        else:
            run_all(binary, args.plugins_dir, args.fixture_base, args.fixture)
        return 0
    except (
        CheckError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        print(f"Authoring fixtures incomplete: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
