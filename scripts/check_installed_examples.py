#!/usr/bin/env python3
"""Finite installed-example inventory, real packages and deterministic providers only.

Accept the source checker's repository/binary arguments plus explicit admin and
fixture storage. Every maintained example has an explicit required runner.
All fixtures and command transcripts are retained; no operational home is used.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from dataclasses import dataclass
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import Iterator

import yaml

from check_examples import (
    CheckError,
    ROOT,
    configure_static_home,
    inspect_graph,
    isolated_environment,
    plugin_manifests,
    stage_plugin,
)
from explanation_snapshot import render

INVENTORY = {
    "edge_fault_advisory": "installed document review + local OpenAI transport",
    "ai_agent_plugins_canary": "seven real installed participants + fake providers",
    "cursor_ticket_delivery": "full installed delivery graph + deterministic providers",
    "hotfix_ticket_delivery": "full installed hotfix graph + deterministic providers",
}
TEXT = "  diagnostic café\r\nsecond line ☃\n\n"
ANSWER = "AI agent plugin canary: OK."
TERMINAL = {"success", "failed", "canceled"}


def peer_helper_source(checkout: Path) -> tuple[Path, bytes]:
    """Read the exact contained helper in an explicit nonsymlink checkout root."""
    from check_examples import contained_file

    require(
        checkout.is_absolute() and checkout.is_dir() and not checkout.is_symlink(),
        "peer helper checkout must be an existing absolute nonsymlink directory",
    )
    path = contained_file(checkout.resolve(), "tests/namespace_peers.py")
    return path, path.read_bytes()


@dataclass(frozen=True)
class PeerHelper:
    """Bind a loaded controller to its selected path and compiled-byte digest."""

    path: Path
    sha256: str
    controller: type
    source: bytes

    def validate(self, checkout: Path) -> None:
        """Reject source drift before dispatch; never relabel loaded code."""
        try:
            path, source = peer_helper_source(checkout)
        except (CheckError, OSError):
            raise CheckError("peer helper source changed since load") from None
        require(
            path == self.path and hashlib.sha256(source).hexdigest() == self.sha256,
            "peer helper source changed since load",
        )


_PEER_HELPERS: dict[Path, PeerHelper] = {}


def peer_controller(checkout: Path) -> PeerHelper:
    """Cache exact captured source; unchanged callers share a class, drift fails.

    Register the module for helper dataclasses, but compile only the captured
    bytes, never a loader reread or bytecode cache. The immutable returned identity
    supplies every receipt; reading current source is only a drift check.
    """
    path, source = peer_helper_source(checkout)
    digest = hashlib.sha256(source).hexdigest()
    if path in _PEER_HELPERS:
        loaded = _PEER_HELPERS[path]
        require(loaded.sha256 == digest, "peer helper source changed since load")
        return loaded
    name = (
        "_fixture_namespace_peers_"
        + hashlib.sha256(str(path).encode()).hexdigest()
        + "_"
        + digest
    )
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "invalid peer helper")
    module = importlib.util.module_from_spec(spec)
    # The helper's explicit loader contract pins this same immutable snapshot
    # before module initialization, controller construction or child dispatch.
    module.__dict__.update(
        __namespace_peers_source__=source,
        __namespace_peers_expected_sha256__=digest,
    )
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec", dont_inherit=True), module.__dict__)
        controller = getattr(module, "NamespacePeers", None)
        require(isinstance(controller, type), "invalid peer helper controller")
        require(
            getattr(module, "SOURCE_BYTES", None) is source
            and getattr(module, "HELPER_SHA256", None) == digest,
            "peer helper requires the captured-source binding API",
        )
        loaded = PeerHelper(path, digest, controller, source)
        loaded.validate(checkout)
    except BaseException:
        del sys.modules[name]
        raise
    _PEER_HELPERS[path] = loaded
    return loaded


# External provider executables, never substitute APP handshakes/action results.
# Production plugin prompt composition, parsing, usage and child lifecycle execute.
PROVIDER = r"""
import datetime, json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
answer = "AI agent plugin canary: OK."
if "--help" in args:
    print("--output-format json\n--stream on")
    raise SystemExit(0)
if name == "opencode" and args[0] == "export":
    print("{}")
    raise SystemExit(0)
prompt = sys.stdin.read() if name in ("ollama", "codex") else " ".join(args)
assert answer in prompt, "prompt did not reach provider"
if name == "gh":
    assert args[:2] == ["copilot", "--"]
    assert "--output-format" in args and "--stream" in args
    # Usage comes from the provider's isolated session-state format.
    state = Path(os.environ["COPILOT_SESSION_STATE_DIR"]) / "fixture"
    state.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    events = [
        {"type":"session.start", "timestamp":now,
         "data":{"sessionId":"fixture", "context":{"cwd":os.getcwd()}}},
        {"type":"session.shutdown", "timestamp":now, "data":{"modelMetrics":{"fixture":{
            "usage":{"inputTokens":3,"outputTokens":2}}}}},
    ]
    (state / "events.jsonl").write_text("\n".join(map(json.dumps, events)) + "\n")
    print(json.dumps({"type":"assistant.message", "data":{"content":answer}}))
elif name == "opencode":
    print(json.dumps({"type":"text", "sessionID":"fixture",
                      "part":{"text":answer}}))
    print(json.dumps({"type":"step_finish", "sessionID":"fixture",
        "part":{"tokens":{"input":3,"output":2,"total":5}}}))
elif name == "cursor-agent":
    print(json.dumps({"type":"system","subtype":"init","model":"fixture"}))
    print(json.dumps({"type":"result","result":answer,"session_id":"fixture",
        "usage":{"inputTokens":3,"outputTokens":2,"totalTokens":5}}))
elif name == "ollama":
    assert args[:1] == ["run"]
    print(answer)
elif name == "codex":
    assert args[:2] == ["exec", "-"]
    assert "--output-last-message" in args
    Path(args[args.index("--output-last-message") + 1]).write_text(answer)
    now = datetime.datetime.now(datetime.timezone.utc)
    state = Path(os.environ["CODEX_HOME"]) / "sessions" / now.strftime("%Y/%m/%d")
    state.mkdir(parents=True, exist_ok=True)
    events = [
        {"type":"session_meta", "payload":{"originator":"codex_cli_rs",
                                           "model_provider":"openai"}},
        {"type":"turn_context", "payload":{"model":"fixture-codex"}},
        {"type":"event_msg", "payload":{"type":"token_count", "info":{
            "total_token_usage":{"input_tokens":3,"output_tokens":2,"total_tokens":5}}}},
    ]
    (state / "rollout-fixture.jsonl").write_text(
        "\n".join(map(json.dumps, events)) + "\n")
else:
    raise AssertionError("unexpected provider executable")
"""


def require(condition: bool, message: str) -> None:
    """Fail a required fixture condition even under optimized Python."""
    if not condition:
        raise CheckError(message)


def _exception_details(error: BaseException) -> dict[str, object]:
    """Extract bounded exception metadata without messages, locals or source text.

    Never serialize exception messages, filenames supplied to OSError, subprocess
    arguments/output, frame locals or source lines: they may contain credentials
    or provider payloads. The final stack location identifies the failing call.
    """
    frames = [
        {
            "file": Path(frame.f_code.co_filename).name,
            "function": frame.f_code.co_name,
            "line": line,
        }
        for frame, line in traceback.walk_tb(error.__traceback__)
    ][-32:]
    record = {
        "error_type": type(error).__name__,
        "errno": (
            error.errno
            if isinstance(error, OSError) and isinstance(error.errno, int)
            else None
        ),
        "traceback": frames,
    }
    observation = getattr(error, "fixture_process_observation", None)
    if type(observation) is dict:
        record["process_observation"] = {
            key: observation[key]
            for key in (
                "parent_pid",
                "parent_birth",
                "child_pid",
                "child_birth",
                "observed_birth",
                "observed_parent",
                "status_pid",
                "status_tgid",
                "status_parent",
                "after_birth",
                "after_parent",
                "inspection_failed",
            )
            if key in observation
            and (type(observation[key]) is int or observation[key] is None)
        }
    return record


def record_failure(error: Exception, base: Path) -> Path:
    """Write a private failure receipt, including causes hidden by cleanup errors."""
    record = _exception_details(error)
    related = []
    pending = [(0, error)]
    seen = {id(error)}
    while pending and len(related) < 8:
        parent, current = pending.pop()
        for relationship, linked in (
            ("cause", current.__cause__),
            ("context", current.__context__),
        ):
            if linked is None or id(linked) in seen or len(related) == 8:
                continue
            seen.add(id(linked))
            related.append(
                {
                    **_exception_details(linked),
                    "parent": parent,
                    "relationship": relationship,
                }
            )
            pending.append((len(related), linked))
    record["related_exceptions"] = related
    fd, name = tempfile.mkstemp(prefix="installed-failure-", suffix=".json", dir=base)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    return Path(name)


def select(examples: list[str]) -> list[str]:
    """Select once in finite inventory order; missing runners fail closed."""
    require(not set(examples) - INVENTORY.keys(), "unknown example selector")
    selected = [name for name in INVENTORY if not examples or name in examples]
    pending = [name for name in selected if INVENTORY[name] is None]
    require(not pending, "installed fixtures unavailable: " + ", ".join(pending))
    return selected


def fixture_python() -> Path:
    """Resolve the real interpreter executable for sandbox-visible fixture shebangs."""
    path = Path(sys.executable).resolve(strict=True)
    require(path.is_file() and os.access(path, os.X_OK), "fixture Python unavailable")
    return path


def executable(path: Path, identity: str) -> Path:
    """Require an explicit 0.1.1 binary; version alone is not provenance."""
    require(
        path.is_absolute() and path.is_file() and os.access(path, os.X_OK),
        f"{identity} must be an absolute executable path",
    )
    result = subprocess.run(
        [str(path), "--version"],
        capture_output=True,
        timeout=15,
        env={"PATH": os.defpath, "NO_COLOR": "1"},
    )
    require(
        result.returncode == 0
        and result.stdout.strip() == f"{identity} 0.1.1".encode(),
        f"{identity} must report version 0.1.1",
    )
    print(f"BINARY {identity} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    return path.resolve()


class Chat(http.server.BaseHTTPRequestHandler):
    """Local OpenAI/Anthropic wire endpoints, recording every external call."""

    def do_POST(self) -> None:
        """Capture the decoded JSON without altering UTF-8 content or whitespace."""
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append({"path": self.path, "body": body})
        response = (
            {
                "type": "message",
                "role": "assistant",
                "id": "fixture",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": ANSWER}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
                "model": "fixture",
            }
            if self.path == "/v1/messages"
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
        """Keep fixture payloads out of access logs."""


@contextmanager
def provider() -> Iterator[http.server.ThreadingHTTPServer]:
    """Own a loopback-only server and join it before leaving the fixture."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Chat)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        require(not thread.is_alive(), "local provider did not stop")


class Driver:
    """Retain one isolated installed home and bounded CLI transcript per fixture."""

    def __init__(self, binary: Path, plugins: Path, base: Path, name: str) -> None:
        self.peer_helper = peer_controller(plugins)
        self.root = Path(tempfile.mkdtemp(prefix=name + "-", dir=base)).resolve()
        self.binary = binary
        self.plugins = plugins
        self.home = self.root / "home"
        self.workspace = self.root / "workspace"
        self.source = self.root / "source"
        self.workspace.mkdir()
        self.source.mkdir()
        self.env = isolated_environment(self.root)
        self.env.update(
            OPENAI_COMPATIBLE_API_KEY="dummy-chat-fixture",
            OPENROUTER_KEY_PERSONAL="dummy-openrouter-fixture",
            ANTHROPIC_API_KEY="dummy-anthropic-fixture",
        )
        self.runs: list[str] = []
        self.sequence = 0
        self.transport = None
        self.transport_sequence = 0
        print(f"FIXTURE {name}: {self.root}", flush=True)
        self.cli("home", "init", "--mode", "standalone")
        configure_static_home(self.home)

    def cli(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess:
        """Run current CLI with explicit isolated storage; retain stdout/stderr."""
        dispatch = self.transport.run if self.transport is not None else subprocess.run
        result = dispatch(
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
            stdout = json.loads(result.stdout)
        except ValueError:
            stdout = result.stdout
        (self.root / f"command-{self.sequence:03}.json").write_text(
            json.dumps(
                {
                    "args": args,
                    "exit": result.returncode,
                    "stdout": stdout,
                    "stderr": result.stderr,
                },
                indent=2,
            )
        )
        require(
            not ok or result.returncode == 0,
            f"CLI {' '.join(args[:2])} failed; inspect fixture command transcript",
        )
        return result

    @contextmanager
    def peers(self, servers: list[http.server.HTTPServer]) -> Iterator[None]:
        """Own exact test peers through run settlement, with no namespace fallback.

        Linux shims/fake executables live outside Git in one explicitly read-only
        fixture tool grant. Each controller uses a fresh subdirectory. Darwin's
        dispatch/environment remain passthrough. Selected plugin bytes stay real.
        """
        require(self.transport is None, "overlapping fixture peer controllers")
        self.peer_helper.validate(self.plugins)
        controller = self.peer_helper.controller
        self.transport_sequence += 1
        identity = json.dumps(
            {"path": str(self.peer_helper.path), "sha256": self.peer_helper.sha256},
            sort_keys=True,
        )
        (self.root / "peer-helper.json").write_text(identity + "\n")
        (self.root / f"peer-helper-{self.transport_sequence}.json").write_text(
            identity + "\n"
        )
        tools = self.root / "bin" / f"namespace-{self.transport_sequence}"
        receipt = self.root / f"namespace-peers-{self.transport_sequence}.json"
        original_env = self.env
        with controller(servers, tools, [self.home / "plugins"], receipt) as transport:
            self.transport = transport
            self.env = transport.environment(original_env)
            config = self.home / "config.yaml"
            settings = yaml.safe_load(config.read_text())
            child = settings["policy"].setdefault(
                "child_env", {"inherit": False, "allowlist": []}
            )
            if "PATH" not in child["allowlist"]:
                child["allowlist"].append("PATH")
            config.write_text(yaml.safe_dump(settings))
            try:
                yield
            finally:
                try:
                    self.close()
                finally:
                    self.transport = None
                    self.env = original_env

    def install_plugins(self, workflow: Path) -> None:
        """Install complete real payloads once and verify selected installed bytes."""
        _, pins, actions = inspect_graph(workflow)
        for manifest in plugin_manifests(self.plugins, pins, actions):
            staged = stage_plugin(manifest, self.root, self.env)
            self.cli("plugins", "install", "--path", str(staged))
            meta = yaml.safe_load(staged.read_text())
            installed = self.home / "plugins" / meta["id"] / meta["version"]
            for name in ("plugin.yaml", *meta["package"]["files"]):
                require(
                    (installed / name).read_bytes()
                    == (staged.parent / name).read_bytes(),
                    "installed plugin differs from explicitly staged payload",
                )
            files = {
                name: hashlib.sha256((installed / name).read_bytes()).hexdigest()
                for name in ("plugin.yaml", *meta["package"]["files"])
            }
            inventory = json.dumps(files, sort_keys=True, indent=2)
            (self.root / (meta["id"] + "-payload.json")).write_text(inventory)
            print(
                f"PAYLOAD {meta['id']}@{meta['version']} "
                f"inventory_sha256={hashlib.sha256(inventory.encode()).hexdigest()}"
            )

    def install_flow(self, flow: dict, name: str) -> str:
        """Install a fresh fixture identity; never replace a same-version package."""
        flow = copy.deepcopy(flow)
        flow["id"] = name
        if sys.platform == "linux":
            # Test infrastructure only: exact fake tools, never the parent/home,
            # target Git tree, operational documents, or an extra network grant.
            tools = self.root / "bin"
            tools.mkdir(exist_ok=True)
            policy = flow.setdefault("filesystem_policy", {})
            policy.setdefault("read_allow_paths", []).append(str(tools))
        path = self.source / (name + ".yaml")
        path.write_text(yaml.safe_dump(flow, sort_keys=False))
        self.cli("workflows", "check", "--path", str(path))
        self.cli("workflows", "install", "--path", str(path), "--approve")
        return f"{name}@{flow['version']}"

    def explanation(self, workflow: Path) -> None:
        """Check the portable snapshot against two real deterministic CLI reports."""
        reports = [
            self.cli("workflows", "explain", "--path", str(workflow)).stdout
            for _ in range(2)
        ]
        require(reports[0] == reports[1], "CLI explanation is not deterministic")
        snapshot = render(json.loads(reports[0]))
        (self.root / "explanation.json").write_text(reports[0])
        (self.root / "explanation.txt").write_text(snapshot)
        require(
            snapshot == (workflow.parent / "explanation.txt").read_text(),
            "generated explanation differs from checked-in snapshot",
        )

    def start(self, reference: str, name: str, inputs: dict) -> dict:
        """Require live readiness before creating an installed fixture run."""
        path = self.root / (name + "-bindings.json")
        path.write_text(json.dumps(inputs))
        checked = json.loads(
            self.cli(
                "workflows", "check", reference, "--inputs-file", str(path), "--live"
            ).stdout
        )
        require(checked["status"] == "ready", "installed readiness is incomplete")
        self.cli(
            "workflows", "run", reference, "--run-ref", name, "--inputs-file", str(path)
        )
        self.runs.append(name)
        return self.wait(name)

    def wait(self, name: str) -> dict:
        """Wait for a durable blocked/terminal state; timeout is a failure."""
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = json.loads(self.cli("runs", "show", name).stdout)
            if state["status"] in TERMINAL | {"blocked"}:
                return state
            time.sleep(0.05)
        raise CheckError("installed run did not settle")

    def decide(self, name: str, decision: str) -> dict:
        """Record a fake-fixture decision and resume through the public CLI."""
        self.cli(
            "runs",
            "gate",
            decision,
            name,
            "diagnostic-transfer",
            "--actor",
            "fixture-reviewer",
            "--reason",
            "offline fixture decision",
        )
        return self.wait(name)

    def head(self, name: str, document: str) -> dict:
        """Read committed document metadata from the fixture's runtime store."""
        path = self.home / "runs" / ("run_" + name) / "documents/heads.json"
        return json.loads(path.read_text())[document]

    def blob(self, name: str, revision: dict) -> bytes:
        """Read exact immutable bytes selected by a committed revision digest."""
        path = self.home / "runs" / ("run_" + name) / "documents/blobs"
        return (path / revision["blob"]["sha256"]).read_bytes()

    def close(self) -> None:
        """Cancel blocked/running fixtures and require terminal settlement."""
        for name in self.runs:
            state = json.loads(self.cli("runs", "show", name).stdout)
            if state["status"] == "blocked":
                self.cli(
                    "runs",
                    "gate",
                    "reject",
                    name,
                    "--actor",
                    "fixture-reviewer",
                    "--reason",
                    "offline fixture cleanup",
                )
                require(self.wait(name)["status"] in TERMINAL, "fixture cleanup failed")
            elif state["status"] not in TERMINAL:
                self.cli("runs", "cancel", name)
                require(self.wait(name)["status"] in TERMINAL, "fixture cleanup failed")


def local_network(port: int) -> dict:
    """Return exact loopback authority for the one fake HTTP listener."""
    return {
        "mode": "loopback",
        "allow_hosts": ["127.0.0.1"],
        "allow_ports": [port],
        "tls_required": False,
        "max_redirects": 0,
    }


def review(state: dict) -> dict:
    """Require the genuine waiting advisory request, not arbitrary workspace input."""
    require(state["status"] == "blocked", "advisory did not wait for approval")
    step = state["steps"]["diagnostic_transfer"]
    require(step["status"] == "blocked", "wrong blocking step")
    request = step["last_result"]["output"]["review_request"]
    require(
        request["step_id"] == "diagnostic_transfer"
        and request["gate_id"] == "diagnostic-transfer",
        "wrong gate identity",
    )
    require(len(request["review_documents"]) == 1, "missing exact document review")
    return request


def source_regressions(driver: Driver, original: dict) -> None:
    """Actual compiler rejects malformed/unknown selectors and missing script assets."""
    bindings = (
        "--input",
        f"workspace_path={driver.workspace}",
        "--input",
        "model=fixture",
    )
    valid = driver.source / "valid-source.yaml"
    valid.write_text(yaml.safe_dump(original))
    positive = json.loads(
        driver.cli("workflows", "check", "--path", str(valid), *bindings).stdout
    )
    require(
        any(check["status"] == "deferred_to_dispatch" for check in positive["checks"]),
        "actual managed-document payload was not reported deferred",
    )
    for index, value in enumerate(
        (
            "{{steps.absent.out.text}}",
            "{{steps.read_diagnostics.bad}}",
            "{{vars.absent}}",
        )
    ):
        flow = copy.deepcopy(original)
        flow["steps"][-1]["with"]["model"] = value
        path = driver.source / f"invalid-{index}.yaml"
        path.write_text(yaml.safe_dump(flow))
        require(
            driver.cli(
                "workflows",
                "check",
                "--path",
                str(path),
                *bindings,
                ok=False,
            ).returncode
            != 0,
            "malformed/unknown data dependency passed source checking",
        )
    flow = copy.deepcopy(original)
    flow["steps"][0] = {
        "id": "bad_script",
        "uses": "process:shell/exec",
        "with": {"command": "python3", "args": ["source://missing.py"]},
    }
    path = driver.source / "invalid-script.yaml"
    path.write_text(yaml.safe_dump(flow))
    require(
        driver.cli(
            "workflows", "check", "--path", str(path), *bindings, ok=False
        ).returncode
        != 0,
        "missing script passed source checking",
    )


def edge(binary: Path, plugins: Path, base: Path) -> None:
    """Exercise approval, rejection, changed publication and waiting restart."""
    from installed_delivery import DeliveryDriver

    workflow = ROOT / "examples/edge_fault_advisory/workflow.yaml"
    original = yaml.safe_load(workflow.read_text())
    # A durable blocked state can precede runner exit/lease release on Linux.
    driver = DeliveryDriver(binary, plugins, base, "edge")
    try:
        driver.install_plugins(workflow)
        driver.explanation(workflow)
        source_regressions(driver, original)
        with provider() as server, driver.peers([server]):
            flow = copy.deepcopy(original)
            advise = flow["steps"][-1]
            advise["network"] = local_network(server.server_port)
            advise["with"]["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
            flow["steps"][1]["with"]["destination"] = advise["with"]["base_url"]
            reference = driver.install_flow(flow, "edge_fixture")
            inputs = {
                "workspace_path": str(driver.workspace),
                "model": "fixture",
                "diagnostic_path": "diagnostics.txt",
            }
            for scenario in ("approved", "rejected", "resumed", "changed"):
                name = "edge_" + scenario
                selected = reference
                if scenario == "changed":
                    changed = copy.deepcopy(flow)
                    # Real successful producer publishes a NEW revision after approval.
                    writer = copy.deepcopy(changed["steps"][0])
                    writer["id"] = "publish_after_review"
                    writer["with"]["path"] = "replacement.txt"
                    changed["steps"].insert(2, writer)
                    selected = driver.install_flow(changed, "edge_changed_fixture")
                    (driver.workspace / "replacement.txt").write_bytes(
                        b"new document\n"
                    )
                (driver.workspace / "diagnostics.txt").write_bytes(TEXT.encode())
                before = len(server.requests)
                state = driver.start(selected, name, inputs)
                request = review(state)
                revision = request["review_documents"][0]
                require(revision["document"] == "diagnostic", "wrong reviewed document")
                require(
                    driver.blob(name, revision) == TEXT.encode(), "review bytes changed"
                )
                require(
                    len(server.requests) == before, "provider called before approval"
                )
                require(
                    state["steps"]["advise"]["executions"] == 0,
                    "consumer dispatched before approval",
                )
                # Later source-workspace changes must not affect reviewed bytes.
                (driver.workspace / "diagnostics.txt").write_bytes(
                    b"unreviewed workspace\n"
                )
                if scenario == "resumed":
                    driver.cli("runs", "start", name)
                    require(
                        review(driver.wait(name)) == request,
                        "waiting restart changed review",
                    )
                    require(
                        len(server.requests) == before, "waiting resume called provider"
                    )
                final = driver.decide(
                    name, "reject" if scenario == "rejected" else "approve"
                )
                if scenario in {"rejected", "changed"}:
                    require(
                        final["status"] == "failed",
                        "unreviewed consumer did not fail closed",
                    )
                    require(
                        len(server.requests) == before,
                        "unapproved bytes reached provider",
                    )
                    if scenario == "changed":
                        head = driver.head(name, "diagnostic")
                        require(
                            head["revision_id"] != revision["revision_id"],
                            "no new revision published",
                        )
                        require(
                            driver.blob(name, head) == b"new document\n",
                            "wrong replacement bytes",
                        )
                        require(
                            "not covered" in json.dumps(final["steps"]["advise"]),
                            "failure was not review-revision enforcement",
                        )
                else:
                    require(final["status"] == "success", "approved advisory failed")
                    require(
                        len(server.requests) == before + 1, "wrong provider call count"
                    )
                    body = server.requests[-1]["body"]
                    require(
                        server.requests[-1]["path"] == "/v1/chat/completions",
                        "unexpected OpenAI transport destination",
                    )
                    require(
                        body["messages"]
                        == [
                            {
                                "role": "system",
                                "content": advise["with"]["system_prompt"],
                            },
                            {"role": "user", "content": TEXT},
                        ],
                        "exact reviewed bytes/system role did not reach provider",
                    )
                    require(
                        driver.blob(name, driver.head(name, "response"))
                        == ANSWER.encode(),
                        "managed provider response was not published",
                    )
                    require(
                        final["steps"]["advise"]["last_result"]["usage"]["total_tokens"]
                        == 5,
                        "provider usage lost",
                    )
                print(
                    f"PASS edge {scenario}; "
                    f"external_calls={len(server.requests) - before}",
                    flush=True,
                )
            (driver.root / "provider-observations.json").write_text(
                json.dumps(server.requests, indent=2)
            )
    finally:
        driver.close()


def canary(binary: Path, plugins: Path, base: Path) -> None:
    """Dispatch seven real installed participants with fake CLI/HTTP boundaries."""
    from installed_delivery import DeliveryDriver

    workflow = ROOT / "examples/ai_agent_plugins_canary/workflow.yaml"
    original = yaml.safe_load(workflow.read_text())
    driver = DeliveryDriver(binary, plugins, base, "canary")
    try:
        fake = driver.root / "bin"
        fake.mkdir()
        for name in ("gh", "copilot", "opencode", "cursor-agent", "ollama", "codex"):
            path = fake / name
            path.write_text(f"#!{fixture_python()}\n" + PROVIDER)
            path.chmod(0o755)
        driver.env["PATH"] = str(fake) + os.pathsep + driver.env["PATH"]
        driver.env["CURSOR_AGENT_PATH"] = str(fake / "cursor-agent")
        codex_home = driver.root / "codex-home"
        codex_home.mkdir()
        driver.env["CODEX_HOME"] = str(codex_home)
        config = driver.home / "config.yaml"
        meta = yaml.safe_load(config.read_text())
        meta["policy"]["child_env"] = {
            "inherit": False,
            "allowlist": ["PATH", "CURSOR_AGENT_PATH", "CODEX_HOME"],
        }
        config.write_text(yaml.safe_dump(meta))
        driver.install_plugins(workflow)
        driver.explanation(workflow)
        shutil.copyfile(workflow.parent / "prompt.md", driver.source / "prompt.md")
        with provider() as server, driver.peers([server]):
            flow = copy.deepcopy(original)
            # Fake CLI tools need no egress; HTTP participants use only this listener.
            for step in flow["steps"]:
                step["network"] = {"mode": "none"}
            routes = {
                "anthropic_canary": ("/v1/messages", "fixture", ""),
                "openai_compatible_canary": ("/v1/chat/completions", "fixture", "/v1"),
            }
            for step in flow["steps"]:
                if step["id"] == "codex_canary":
                    step["filesystem_policy"] = {"write_allow_paths": [str(codex_home)]}
                if step["id"] in routes:
                    step["network"] = local_network(server.server_port)
                    step["with"]["base_url"] = (
                        f"http://127.0.0.1:{server.server_port}" + routes[step["id"]][2]
                    )
            reference = driver.install_flow(flow, "canary_fixture")
            inputs = {
                "repo_path": str(driver.workspace),
                **{
                    name + "_model": "fixture"
                    for name in (
                        "github_copilot",
                        "opencode",
                        "ollama",
                        "cursor",
                        "anthropic",
                        "codex",
                        "openai_compatible",
                    )
                },
            }
            # Two fresh runs prove invocation-local history remains usable repeatedly.
            for number in range(2):
                before = len(server.requests)
                state = driver.start(reference, f"canary_{number}", inputs)
                require(
                    state["status"] == "success",
                    "canary participant failed; inspect retained state",
                )
                require(
                    set(state["steps"]) == {step["id"] for step in original["steps"]},
                    "canary participant inventory changed",
                )
                for step in original["steps"]:
                    recorded = state["steps"][step["id"]]
                    result = recorded["last_result"]
                    payload = recorded["last_request"]["input"]
                    require(
                        result["output"]["response_text"].strip() == ANSWER,
                        "canary provider returned unexpected content",
                    )
                    if step["id"] not in routes:
                        require(
                            payload["max_prompt_bytes"] == 98304,
                            "prompt budget changed",
                        )
                        if step["id"] != "ollama_canary":
                            require(
                                payload["history_mode"] == "invocation"
                                and payload["max_context_file_bytes"] == 65536,
                                "history or context budget changed",
                            )
                        require(
                            result["output"].get("output_mode") == "compact",
                            "lean output lost",
                        )
                        require(
                            "stdout" not in result["output"]
                            and "stderr" not in result["output"],
                            "raw transport escaped compact mode",
                        )
                    if step["id"] != "ollama_canary":
                        require(
                            result.get("usage", {}).get("total_tokens") == 5,
                            "provider usage lost",
                        )
                requests = server.requests[before:]
                require(len(requests) == len(routes), "wrong HTTP provider call count")
                for step_id, (path, model, suffix) in routes.items():
                    matches = [
                        request for request in requests if request["path"] == path
                    ]
                    require(len(matches) == 1, "unexpected HTTP provider route")
                    body = matches[0]["body"]
                    payload = state["steps"][step_id]["last_request"]["input"]
                    require(
                        payload["base_url"]
                        == f"http://127.0.0.1:{server.server_port}{suffix}"
                        and payload["model"] == model
                        and body["model"] == model,
                        "HTTP provider model or base URL changed",
                    )
                    require(
                        payload["max_tokens"] == 64 and body["max_tokens"] == 64,
                        "HTTP provider output budget changed",
                    )
                print(
                    f"PASS canary run {number}: "
                    "seven participants, compact output/usage",
                    flush=True,
                )
            require(
                not list(driver.workspace.iterdir()),
                "canary wrote operational workspace data",
            )
            (driver.root / "provider-observations.json").write_text(
                json.dumps(server.requests, indent=2)
            )
    finally:
        driver.close()


def main(argv: list[str] | None = None) -> int:
    """Run selected installed fixtures; missing prerequisites/pending inventory fail."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", "--transist-bin", required=True, type=Path)
    parser.add_argument("--admin-bin", "--transist-admin", required=True, type=Path)
    parser.add_argument("--plugins-dir", required=True, type=Path)
    parser.add_argument("--fixture-base", "--home-base", required=True, type=Path)
    parser.add_argument(
        "--example", action="append", choices=sorted(INVENTORY), default=[]
    )
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(
            not os.environ.get("PYTHONOPTIMIZE") and __debug__,
            "assertions must be enabled",
        )
        binary = executable(args.transist, "transist")
        executable(args.admin_bin, "transist-admin")
        require(
            args.plugins_dir.is_absolute() and args.plugins_dir.is_dir(),
            "plugins-dir is missing",
        )
        base = args.fixture_base
        require(
            base.is_absolute() and base.is_dir() and not base.is_symlink(),
            "fixture-base must be an existing absolute nonsymlink directory",
        )
        if args.list:
            for name, description in INVENTORY.items():
                print(f"{name}: {description or 'UNAVAILABLE (selection fails)'}")
            return 0
        selected = select(args.example)
        for name in selected:
            if name in {"cursor_ticket_delivery", "hotfix_ticket_delivery"}:
                from installed_delivery import run

                run(binary, args.plugins_dir, base.resolve(), name)
            else:
                {"edge_fault_advisory": edge, "ai_agent_plugins_canary": canary}[name](
                    binary, args.plugins_dir, base.resolve()
                )
        if not args.example:
            from check_authoring_fixtures import run_all

            run_all(binary, args.plugins_dir, base.resolve())
        print(f"RESULT {len(selected)} installed examples passed; zero skips")
        return 0
    except Exception as error:
        message = str(error) if isinstance(error, CheckError) else type(error).__name__
        print(f"Installed examples incomplete: {message}", file=sys.stderr)
        try:
            receipt = record_failure(error, args.fixture_base)
        except OSError:
            print("Failure diagnostic could not be retained", file=sys.stderr)
        else:
            print(
                f"Failure diagnostic in fixture-base: {receipt.name}", file=sys.stderr
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
