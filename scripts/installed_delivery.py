#!/usr/bin/env python3
"""Full maintained delivery graphs against deterministic external CLI/HTTP peers.

Every action, module, prompt and captured helper remains real. Git network verbs
are fake; local Git queries/staging/commits execute the native binary. All service
state lives in the fixture-owned loopback server, outside the target repository.
"""

from __future__ import annotations

from contextlib import contextmanager
import base64
import copy
import hashlib
import http.server
import json
import os
from pathlib import Path
import platform
import re
import select
import shutil
import socket
import subprocess
import struct
import sys
import threading
import time
import traceback
from typing import Iterator

import yaml

from check_installed_examples import (
    CheckError,
    Driver,
    ROOT,
    TERMINAL,
    fixture_python,
    local_network,
    require,
)
from explanation_snapshot import render
from source_identity import source_identity

ATTACHMENT = b"exact attachment caf\xc3\xa9\r\n"
REQUEST = "  Preserve this pre-gate request.\nExact caf\u00e9 scope.  "
REPLY = "The requested boundary is retained; this is a synthetic clarification."
URL = "https://github.com/fixture/fixture/pull/7"
DIFF_HEADER = "@@ -1 +1 @@"
# Keep the synthetic located requests until the first request-changes gate has
# caused the real scanner to publish them for the next implementation iteration.
INSTRUCTION_SOURCE = (
    "# tst: hash-request\n// tst: slash-request\n-- tst: sql-request\n"
    "/* tst: block-request */\n<!-- tst: html-request -->\n"
    'value = "# tst: quoted-not-request"\ncode() # tst: trailing-not-request\n'
)
RECOVERY_CASES = {
    "retry": ("retry", "conversation"),
    "resume": ("resume", "conversation"),
    "retry_review_thread": ("retry", "review_thread"),
    "resume_review_thread": ("resume", "review_thread"),
}


def expose_native_awk(tools: Path, env: dict[str, str]) -> None:
    """Alias the real system awk leaf inside the existing fixture-only tool grant.

    Debian's /usr/bin/awk resolves through /etc/alternatives, which is deliberately
    hidden by the sandbox. Keep the exact real executable and arguments, without
    mounting alternatives, changing the shell helper, or fabricating its output.
    Record the resolved binary hash outside the target Git workspace.
    """
    found = shutil.which("awk", path=env["PATH"])
    require(found is not None, "delivery fixture requires a real native awk")
    native = Path(found).resolve(strict=True)
    require(native.is_file() and os.access(native, os.X_OK), "native awk unavailable")
    alias = tools / "awk"
    require(not alias.exists() and not alias.is_symlink(), "fixture awk already exists")
    alias.symlink_to(native)
    (tools.parent / "native-tools.json").write_text(
        json.dumps(
            {
                "awk": {
                    "resolved": str(native),
                    "sha256": hashlib.sha256(native.read_bytes()).hexdigest(),
                }
            },
            indent=2,
        )
        + "\n"
    )


def required_scenarios(example: str) -> tuple[str, ...]:
    """Return the finite mandatory matrix; both lost-reply surfaces are required."""
    common = ("reject", "validation", "success", "changes", "retry", "resume")
    return common + (
        ("retry_review_thread", "resume_review_thread", "legacy")
        if example == "cursor_ticket_delivery"
        else ()
    )


# Only external executables are fake. They communicate through one loopback peer;
# production APP handlers, schema checks, parsing and subprocess ownership run.
PEER = r"""
import datetime, json, os, subprocess, sys, urllib.request
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
def call(kind, extra=None):
    payload = {"tool":name,"args":args,"cwd":os.getcwd(), **(extra or {})}
    request = urllib.request.Request(BASE + "/" + kind,
        json.dumps(payload).encode(), {"Content-Type":"application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)
if name == "git":
    if args and args[0] in {"fetch","push","pull","ls-remote"}:
        result = {"stdout":"","stderr":"","code":0}
    else:
        completed = subprocess.run([REAL_GIT, *args], capture_output=True, text=True)
        result = {"stdout":completed.stdout,"stderr":completed.stderr,
                  "code":completed.returncode}
    extra = {"result":result}
    if args and args[0] in {"add","commit"}:
        staged = subprocess.run([REAL_GIT,"ls-files","--cached","-z"],
            capture_output=True, text=True, check=True).stdout
        extra["tracked"] = staged.split("\0")
    remote = call("git", extra)
    if args[:1] == ["pull"] and args[-1:] == ["main"] and remote.get("merged"):
        completed = subprocess.run([REAL_GIT,"merge","--ff-only","PROJ-123"],
            capture_output=True, text=True)
        result = {"stdout":completed.stdout,"stderr":completed.stderr,
                  "code":completed.returncode}
elif "--help" in args:
    result = {"stdout":"--output-format json\n--stream on\n", "code":0}
elif "--version" in args:
    result = {"stdout":name + " fixture\n", "code":0}
elif name == "openspec":
    assert args[0] == "validate"
    assert (Path.cwd()/"openspec/changes"/args[1]/"tasks.md").is_file()
    call("openspec")
    result = {"stdout":"valid synthetic OpenSpec change\n","code":0}
elif name == "gh" and args[:1] != ["copilot"]:
    result = call("gh")
else:
    result = call("agent")
    for filename, text in result.pop("write_files", {}).items():
        path = Path.cwd()/filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    answer = result.pop("answer")
    if name == "gh":
        state = Path(os.environ["COPILOT_SESSION_STATE_DIR"])/"fixture"
        state.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        events = [{"type":"session.start","timestamp":now,"data":{
            "sessionId":"fixture","context":{"cwd":os.getcwd()}}},
            {"type":"session.shutdown","timestamp":now,"data":{"modelMetrics":{
            "fixture":{"usage":{"inputTokens":3,"outputTokens":2}}}}}]
        (state/"events.jsonl").write_text("\n".join(map(json.dumps,events))+"\n")
        result["stdout"] = json.dumps({"type":"assistant.message",
            "data":{"content":answer}}) + "\n"
    elif args[args.index("--output-format")+1] == "text":
        result["stdout"] = answer + "\n"
    else:
        result["stdout"] = json.dumps({"type":"result","result":answer,
            "session_id":"fixture","usage":{"inputTokens":3,"outputTokens":2,
            "totalTokens":5}})+"\n"
sys.stdout.write(result.get("stdout", ""))
sys.stderr.write(result.get("stderr", ""))
raise SystemExit(result.get("code",0))
"""


class _RecoveryBoundary(RuntimeError):
    """A fixture response was withheld and its owning run was publicly canceled."""


def _cleanup_not_started(state: dict) -> bool:
    """Reject cleanup recovery; accept only unstarted empty cancellation metadata."""
    if state.get("recovery_state") not in {None, "recoverable"}:
        return False
    cleanup = state.get("cleanup")
    if cleanup is None:
        return True
    if cleanup.get("steps") != {}:
        return False
    if cleanup.get("state") == "skipped":
        return True
    # The verified public runtime's reset_cleanup_for_primary_activation resets
    # a skipped cancellation descriptor to pending and clears its timestamps.
    # That is a new active primary activation, not started failure cleanup.
    return (
        state.get("status") in {"running", "blocked"}
        and state.get("resume_count", 0) > 0
        and cleanup.get("trigger") == "canceled"
        and cleanup.get("state") == "pending"
        and cleanup.get("started_at_ms") is None
        and cleanup.get("finished_at_ms") is None
        and cleanup.get("preflight") is None
    )


class Service(http.server.BaseHTTPRequestHandler):
    """Own deterministic Jira, GitHub and model state; retain every request."""

    def send(self, body: object, code: int = 200) -> None:
        """Return exact bounded JSON/attachment bytes to the real plugin transport."""
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        """Serve the real Jira plugin's issue, attachment and transition requests."""
        fixture = self.server.fixture
        self.server.request_count += 1
        fixture["requests"].append({"path": self.path, "method": "GET"})
        route = self.path.split("?", 1)[0]
        if route not in {
            "/attachment",
            "/rest/api/3/issue/PROJ-123",
            "/rest/api/3/issue/PROJ-123/transitions",
        }:
            fixture["errors"].append("unexpected Jira GET route")
            self.send({"error": "unexpected route"}, 404)
            return
        if self.headers.get("Authorization") != "dummy-jira-fixture":
            fixture["errors"].append("synthetic Jira credential was not delivered")
            self.send({"error": "missing synthetic credential"}, 401)
            return
        if self.path == "/attachment":
            self.send(ATTACHMENT)
        elif self.path.endswith("/transitions"):
            self.send(
                {
                    "transitions": [
                        {"id": str(index), "name": name, "to": {"name": name}}
                        for index, name in enumerate(
                            ("IN PROGRESS", "Review", "DONE"), 1
                        )
                    ]
                }
            )
        else:
            if fixture["scenario"] == "failure_cleanup":
                self.send({"error": "synthetic transient fetch failure"}, 503)
                return
            if fixture["recovery"] is not None and not fixture["lost"]:
                fixture["lost"] = True
                self.wait_for_cancellation("jira_fetch")
                return
            self.send(
                {
                    "key": "PROJ-123",
                    "fields": {
                        "summary": "Synthetic delivery",
                        "description": None,
                        "attachment": [
                            {
                                "id": "1",
                                "filename": "ticket.txt",
                                "mimeType": "text/plain",
                                "size": len(ATTACHMENT),
                                "content": self.server.base_url + "/attachment",
                            }
                        ],
                    },
                }
            )

    def do_POST(self) -> None:
        """Dispatch fake external boundaries while retaining full real graph input."""
        payload = json.loads(
            self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}"
        )
        fixture = self.server.fixture
        self.server.request_count += 1
        fixture["requests"].append(
            {"path": self.path, "method": "POST", "body": payload}
        )
        try:
            if self.path == "/agent":
                answer = self.agent(payload)
            elif self.path == "/gh":
                answer = self.github(payload["args"])
            else:
                require(
                    self.path
                    in {"/git", "/openspec", "/rest/api/3/issue/PROJ-123/transitions"},
                    "unexpected fixture POST route",
                )
                if self.path == "/git" and "tracked" in payload:
                    fixture["staged"].append(payload["tracked"])
                answer = {"merged": fixture["merged"]} if self.path == "/git" else {}
            pending = answer.pop("_fixture_interrupt", None)
            if pending is not None:
                self.wait_for_cancellation(pending)
                return
            self.send(answer)
        except Exception as error:
            fixture["errors"].append(repr(error))
            self.send({"error": repr(error)}, 500)

    def wait_for_cancellation(self, stage: str) -> None:
        """Withhold a fixture response until public cancellation closes its client.

        No failed action result is delivered before cancellation. This keeps the
        real authored failed-cleanup branch intact while exercising retry/resume
        only from their eligible canceled state. Socket EOF is observed, never
        inferred from a PID announcement or a timer.
        """
        fixture = self.server.fixture
        require(fixture["recovery"] in {"retry", "resume"}, "unplanned recovery")
        require(stage in {"jira_fetch", "reply"}, "unknown recovery stage")
        require(fixture["recovery_pending"] is None, "overlapping recovery barriers")
        fixture["recovery_pending"] = stage
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            readable, _, _ = select.select([self.connection], [], [], 0.05)
            if readable:
                require(
                    self.connection.recv(1, socket.MSG_PEEK) == b"",
                    "unexpected data while fixture response was withheld",
                )
                fixture["recovery_disconnected"].append(stage)
                return
        raise CheckError("public cancellation did not disconnect the fixture client")

    def agent(self, payload: dict) -> dict:
        """Return provider-native text/JSON; inspect actual composed model context."""
        fixture = self.server.fixture
        args = payload["args"]
        prompt = args[args.index("-p") + 1] if "-p" in args else args[-1]
        is_openspec = (
            "--output-format" in args
            and args[args.index("--output-format") + 1] == "text"
        )
        if is_openspec and "summary_markdown" in prompt:
            kind = "plan"
        elif is_openspec:
            kind = "verify"
        elif "Include exactly one result for EVERY actionable comment" in prompt:
            kind = "review"
        elif "draft" in prompt.lower() and (
            "pull request description" in prompt.lower()
            or "final pr body" in prompt.lower()
        ):
            kind = "draft"
        elif "Address unresolved pull request" in prompt:
            kind = "review"
        else:
            kind = "implement"
        fixture["agents"][kind] = fixture["agents"].get(kind, 0) + 1
        count = fixture["agents"][kind]
        if kind == "plan":
            answer = json.dumps(
                {
                    "summary_markdown": "# Approved plan\n\nSynthetic exact plan.",
                    "proposal_markdown": "# Proposal\n\nSynthetic change.",
                    "tasks_markdown": "## Tasks\n- [ ] Implement synthetic fix\n",
                    "design_markdown": "# Design\n\nKeep explicit boundaries.",
                    "specs": [
                        {
                            "capability": "delivery",
                            "spec_markdown": "## ADDED Requirements\n"
                            "### Requirement: Explicit delivery\n"
                            "Keep the boundary.\n#### Scenario: Synthetic delivery\n"
                            "- WHEN the fixture runs\n- THEN preserve the contract\n",
                        }
                    ],
                }
            )
        elif kind == "verify":
            passed = not (fixture["scenario"] == "validation" and count in {1, 3})
            answer = json.dumps(
                {
                    "passed": passed,
                    "report_markdown": "## Verdict\n"
                    + ("PASS" if passed else "FAIL synthetic mismatch"),
                    "findings": [],
                }
            )
        elif kind == "draft":
            header = re.search(r"(?m)^Addresses:.*$", prompt)
            require(
                header is not None, "managed PR header did not reach draft provider"
            )
            answer = (
                header[0] + "\n\n## What Changed\nSynthetic delivery.\n\n"
                "## Verification\nFixture checks."
            )
        else:
            replies = []
            if kind == "review" and fixture["workflow"] == "cursor_ticket_delivery":
                require(
                    any(
                        value in prompt
                        for value in (
                            REQUEST,
                            json.dumps(REQUEST)[1:-1],
                            json.dumps(REQUEST, ensure_ascii=False)[1:-1],
                        )
                    ),
                    "pre-gate request missing from actual model prompt",
                )
                require(
                    DIFF_HEADER in prompt and "R_thread" in prompt,
                    "projected header with null numeric lines was lost "
                    "before model dispatch",
                )
                replies = [
                    {"comment_id": identity, "outcome": "clarification", "reply": REPLY}
                    for identity in ("C_pending", "R_thread")
                ]
            answer = (
                "Implement synthetic delivery\n\n## What Changed\nKeep boundaries.\n"
                "\n## Review Response\nPreserve exact requests.\n\n"
                "## Review Replies\n```json\n"
                + json.dumps(replies)
                + "\n```\n\n## Verification\nFixture checks.\n\n"
                "## Risks\nNone in fixture."
            )
            if (
                fixture["workflow"] == "hotfix_ticket_delivery"
                and fixture["scenario"] == "validation"
            ):
                answer += "x" * 70000
        result = {"answer": answer, "code": 0}
        if kind == "implement" and fixture["scenario"] == "changes" and count == 2:
            require(
                "src/delivery.txt:1" in prompt and "hash-request" in prompt,
                "real scanner's located instruction did not reach the model",
            )
        if kind == "implement" or (
            kind == "review" and fixture["scenario"] in {"changes", "validation"}
        ):
            root_id = re.search(r'"root_run_id"\s*:\s*"([^"]+)"', prompt)
            require(
                root_id is not None,
                "actual root reviewer ledger missing from agent context",
            )
            variant = hashlib.sha256(root_id[1].encode()).hexdigest()[:8]
            result["write_files"] = {
                "src/delivery.txt": f"{kind} fixture {variant} revision {count}\n"
            }
            if kind == "implement" and fixture["scenario"] == "changes" and count == 1:
                result["write_files"]["src/delivery.txt"] = (
                    INSTRUCTION_SOURCE + result["write_files"]["src/delivery.txt"]
                )
        return result

    def github(self, args: list[str]) -> dict:
        """Emulate gh provider commands, including bounded reconciliation GETs."""
        fixture = self.server.fixture
        result = {"code": 0, "stdout": ""}
        pr = {
            "number": 7,
            "state": "MERGED" if fixture["merged"] else "OPEN",
            "url": URL,
            "title": "[PROJ-123] Synthetic delivery",
            "baseRefName": "main",
            "headRefName": "PROJ-123",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [],
        }
        if args[:2] == ["repo", "view"]:
            value = {"owner": {"login": "fixture"}, "name": "fixture"}
        elif args[:2] == ["pr", "view"]:
            ready = (
                fixture["scenario"] not in {"changes", "legacy"}
                and fixture["recovery"] is None
                or fixture["agents"].get("review", 0) > 0
            )
            if fixture["scenario"] == "validation":
                ready = True
            value = {
                **pr,
                "latestReviews": [
                    {"author": {"login": "Reviewer-A"}, "state": "APPROVED"},
                    {"author": {"login": "reviewer-a"}, "state": "CHANGES_REQUESTED"},
                    {"author": {"login": "reviewer-b"}, "state": "APPROVED"},
                    {"author": {"login": "reviewer-b"}, "state": "DISMISSED"},
                    {"state": "APPROVED"},
                ]
                + (
                    [{"author": {"login": "reviewer-c"}, "state": "APPROVED"}]
                    if ready
                    else []
                ),
                "reviews": [],
            }
        elif args[:2] == ["pr", "create"]:
            fixture["pr_body"] = args[args.index("--body") + 1]
            fixture["pr_created_draft"] = "--draft" in args
            # Simulate reviewers making a draft ready before first inspection.
            # No authored ready/approval action is removed or bypassed.
            fixture["remote_ready_transition"] = fixture["pr_created_draft"]
            result["stdout"] = URL + "\n"
            return result
        elif args[:2] == ["pr", "merge"]:
            fixture["merged"] = True
            value = {}
        elif args[:2] == ["pr", "edit"]:
            value = {}
        elif args[:2] == ["api", "graphql"]:
            query = next((arg for arg in args if arg.startswith("query=")), "")
            if "resolveReviewThread" in query:
                value = {
                    "data": {
                        "resolveReviewThread": {
                            "thread": {"id": "T_fixture", "isResolved": True}
                        }
                    }
                }
            else:
                fixture["fetches"] += 1
                comments = []
                conversations = []
                if (
                    fixture["scenario"] in {"changes", "validation", "legacy"}
                    or fixture["recovery"] is not None
                ) and fixture["agents"].get("review", 0) == 0:
                    comments = [
                        {
                            "id": "R_thread",
                            "databaseId": 42,
                            "body": "Clarify the boundary.",
                            "path": "src/delivery.txt",
                            "author": {"login": "reviewer"},
                            "url": URL + "#discussion_r42",
                            "createdAt": "2026-01-01T10:00:00Z",
                            "diffHunk": "@@ -1 +1 @@\nold",
                            "line": None,
                            "originalLine": None,
                        }
                    ]
                    if fixture["fetches"] == 1:
                        conversations = [
                            {
                                "id": "C_pending",
                                "body": REQUEST,
                                "author": {"login": "reviewer"},
                                "url": URL + "#issuecomment-1",
                                "createdAt": "2026-01-01T10:00:00Z",
                            }
                        ]
                value = {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": (
                                        [
                                            {
                                                "id": "T_fixture",
                                                "isResolved": False,
                                                "isOutdated": False,
                                                "comments": {
                                                    "nodes": comments,
                                                    "pageInfo": {"hasNextPage": False},
                                                },
                                            }
                                        ]
                                        if comments
                                        else []
                                    ),
                                    "pageInfo": {"hasNextPage": False},
                                },
                                "conversationComments": {
                                    "nodes": conversations,
                                    "pageInfo": {"hasNextPage": False},
                                },
                            }
                        }
                    }
                }
        elif args[:1] == ["api"]:
            endpoint = next(arg for arg in args[1:] if arg.startswith("repos/"))
            method = (
                args[args.index("-X") + 1]
                if "-X" in args
                else (args[args.index("--method") + 1] if "--method" in args else "GET")
            )
            if "labels/" in endpoint:
                value = {"name": "ai-assisted"}
            elif "/git/refs/" in endpoint:
                value = {}
            elif method == "GET":
                value = [
                    post
                    for post in fixture["posts"]
                    if post["surface"]
                    == ("review_thread" if "/pulls/" in endpoint else "conversation")
                ]
                fixture["publication_events"].append(
                    {
                        "kind": "reply_collection_get",
                        "method": method,
                        "sequence": len(fixture["requests"]) - 1,
                        "endpoint": endpoint,
                        "surface": (
                            "review_thread" if "/pulls/" in endpoint else "conversation"
                        ),
                        "returned": [
                            {"id": post["id"], "body": post["body"]} for post in value
                        ],
                    }
                )
            elif method in {"POST", "PATCH"}:
                body = next(arg[5:] for arg in args if arg.startswith("body="))
                if method == "PATCH":
                    target = next(
                        post
                        for post in fixture["posts"]
                        if str(post["id"]) == endpoint.rsplit("/", 1)[-1]
                    )
                    target["body"] = body
                    value = target
                else:
                    parent = next(
                        (
                            int(arg.split("=", 1)[1])
                            for arg in args
                            if arg.startswith("in_reply_to=")
                        ),
                        None,
                    )
                    value = {
                        "id": len(fixture["posts"]) + 100,
                        "body": body,
                        "html_url": URL
                        + ("#discussion_r" if parent else "#issuecomment-")
                        + str(len(fixture["posts"]) + 100),
                        "user": {"login": "fixture"},
                        "surface": "review_thread" if parent else "conversation",
                    }
                    if parent:
                        value["in_reply_to_id"] = parent
                    fixture["posts"].append(value)
                    lose_response = (
                        fixture["recovery"] is not None
                        and "transist-review-reply" in body
                        and value["surface"] == fixture["loss_surface"]
                        and not fixture["reply_lost"]
                    )
                    if "transist-review-reply" in body:
                        marker = re.search(
                            r"(?m)^<!-- transist-review-publication:[0-9a-f]{64} -->$",
                            body,
                        )
                        require(
                            marker is not None,
                            "publisher omitted the stable identity marker",
                        )
                        event = {
                            "kind": "accepted_reply_post",
                            "method": method,
                            "sequence": len(fixture["requests"]) - 1,
                            "endpoint": endpoint,
                            "surface": value["surface"],
                            "id": value["id"],
                            "marker": marker[0],
                            "body": body,
                            "response_lost": lose_response,
                        }
                        fixture["publication_events"].append(event)
                        if lose_response:
                            fixture["lost_publication"] = event.copy()
                    if lose_response:
                        fixture["reply_lost"] = True
                        return {"_fixture_interrupt": "reply"}
            else:
                raise ValueError("unexpected gh API method")
        else:
            raise ValueError("unexpected gh command: " + repr(args[:3]))
        result["stdout"] = json.dumps(value) + "\n"
        return result

    def log_message(self, *_args: object) -> None:
        """Keep fake payloads in explicit retained observations only."""


@contextmanager
def service(workflow: str) -> Iterator[http.server.ThreadingHTTPServer]:
    """Own one local service and join every request thread on teardown."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Service)
    server.daemon_threads = False
    server.base_url = f"http://127.0.0.1:{server.server_port}"
    server.fixture = {}
    server.request_count = 0
    server.settled = False
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
        require(not thread.is_alive(), "delivery fixture server did not settle")
        server.settled = True


class DeliveryDriver(Driver):
    """Retain runner ownership and inspect the actual nested run tree."""

    def __init__(self, *args: object) -> None:
        self.pids: set[int] = set()
        self.fixture: dict | None = None
        super().__init__(*args)

    def cli(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess:
        """Remember detached runner PIDs, including failed CLI dispatch receipts."""
        result = super().cli(*args, ok=False)
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("runner_pid"), int):
            self.pids.add(payload["runner_pid"])
        require(not ok or result.returncode == 0, f"delivery CLI failed: {args[:2]}")
        return result

    def start(self, reference: str, name: str, inputs: dict) -> dict:
        """Own any born run even when a later dispatch/CLI failure interrupts start."""
        try:
            return super().start(reference, name, inputs)
        finally:
            if (
                self.home / "runs" / ("run_" + name)
            ).exists() and name not in self.runs:
                self.runs.append(name)

    def settle(self) -> None:
        """Wait for runner exit, not just an early durable terminal-state write."""
        deadline = time.monotonic() + 30
        while True:
            if not self.running():
                return
            require(time.monotonic() < deadline, "delivery runners did not exit")
            time.sleep(0.05)

    def running(self) -> bool:
        """Inspect only owned PIDs, tolerating zombie exit and unrelated PID reuse."""
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

    def wait(self, name: str) -> dict:
        """Wait for current durable state and actual runner exit together."""
        deadline = time.monotonic() + 180
        path = self.home / "runs" / ("run_" + name) / "state.json"
        while time.monotonic() < deadline:
            if not path.exists():
                require(self.running(), "delivery runner exited before run birth")
                time.sleep(0.05)
                continue
            state = json.loads(path.read_text())
            if self.fixture is not None and self.fixture.get("recovery_pending"):
                self.cancel_for_recovery(name, state, path)
                raise _RecoveryBoundary("eligible canceled recovery boundary")
            if state["status"] in TERMINAL | {"blocked"} and not self.running():
                return json.loads(self.cli("runs", "show", name).stdout)
            time.sleep(0.1)
        raise ValueError("full delivery segment did not settle within 180 seconds")

    def cancel_for_recovery(self, name: str, before: dict, path: Path) -> None:
        """Publicly cancel running synthetic work and retain eligibility proof."""
        fixture = self.fixture
        require(fixture is not None, "recovery fixture missing")
        stage = fixture["recovery_pending"]
        require(fixture["recovery"] in {"retry", "resume"}, "unplanned cancellation")
        sequence = len(fixture["recovery_interruptions"]) + 1
        prefix = self.root / f"{name}-recovery-{sequence}"
        Path(str(prefix) + "-before.json").write_text(json.dumps(before, indent=2))
        # A parent remains blocked while its resumed contained recipe executes.
        # Require the live owned runner as wait() already does for settlement;
        # neither a terminal root nor an idle manual gate is a response barrier.
        require(
            before["status"] in {"running", "blocked"}
            and self.running()
            and _cleanup_not_started(before),
            "response barrier lacks live eligible primary work",
        )
        self.cli("runs", "cancel", name)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            after = json.loads(path.read_text())
            if after["status"] == "canceled" and not self.running():
                break
            time.sleep(0.05)
        else:
            raise CheckError("public cancellation did not settle the owned runner")
        require(_cleanup_not_started(after), "cancellation began authored cleanup")
        fixture["recovery_pending"] = None
        Path(str(prefix) + "-after.json").write_text(json.dumps(after, indent=2))
        fixture["recovery_interruptions"].append(
            {
                "stage": stage,
                "run_id": name,
                "operation": fixture["recovery"],
                "before_status": before["status"],
                "after_status": after["status"],
                "cleanup_state": (after.get("cleanup") or {}).get("state"),
                "cleanup_steps": sorted((after.get("cleanup") or {}).get("steps", {})),
                "runner_settled": True,
                "transport_sequence": self.transport_sequence,
            }
        )

    def states(self, name: str) -> list[dict]:
        """Read exact committed root/contained states, never guessed child IDs."""
        root = self.home / "runs" / ("run_" + name)
        return [
            json.loads(path.read_text())
            for path in root.rglob("state.json")
            if path.parent.name.startswith("run_")
        ]

    def gate(self, name: str) -> tuple[dict, dict]:
        """Find the genuine current blocked gate in the active nested recipe."""
        for state in self.states(name):
            for step in state["steps"].values():
                if step["status"] == "blocked":
                    request = (
                        (step.get("last_result") or {})
                        .get("output", {})
                        .get("review_request")
                    )
                    if request:
                        return state, request
        raise ValueError("no real blocked delivery gate")

    def close(self) -> None:
        """Cancel every remaining root via public CLI, then await all runners."""
        for name in self.runs:
            birth = self.home / "runs" / ("run_" + name) / "state.json"
            deadline = time.monotonic() + 30
            while not birth.exists() and self.running() and time.monotonic() < deadline:
                time.sleep(0.05)
            if not birth.exists():
                continue
            state = json.loads(self.cli("runs", "show", name).stdout)
            if state["status"] not in TERMINAL:
                self.cli("runs", "cancel", name)
                deadline = time.monotonic() + 30
                while (
                    json.loads(self.cli("runs", "show", name).stdout)["status"]
                    not in TERMINAL
                ):
                    require(
                        time.monotonic() < deadline, "delivery cancel did not settle"
                    )
                    time.sleep(0.05)
        self.settle()
        (self.root / "settled-runners.json").write_text(
            json.dumps({"pids": sorted(self.pids), "all_exited": True})
        )


def git(workspace: Path, *args: str) -> str:
    """Run real local Git for fixture preparation and independent index assertions."""
    return subprocess.run(
        ["/usr/bin/git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env={
            "PATH": os.defpath,
            "HOME": str(workspace),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        },
    ).stdout


def workspace(path: Path, cursor: bool) -> None:
    """Create a genuine clean target repository with synthetic source/config."""
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Fixture")
    git(path, "config", "user.email", "fixture@example.org")
    (path / ".gitignore").write_text(
        "# Managed documents require no workspace exclusion.\n"
    )
    (path / "README.md").write_text("# Synthetic delivery target\n")
    (path / "src").mkdir()
    (path / "src/delivery.txt").write_text(INSTRUCTION_SOURCE)
    if cursor:
        (path / "openspec").mkdir()
        (path / "openspec/config.yaml").write_text("schema: spec-driven\n")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "Synthetic baseline")
    git(path, "remote", "add", "origin", "https://github.com/fixture/fixture.git")


def fixture_state(example: str, scenario: str) -> dict:
    """Create independent service state without changing workflow inputs or steps."""
    state = {
        "workflow": example,
        "scenario": scenario,
        "agents": {},
        "requests": [],
        "posts": [],
        "staged": [],
        "fetches": 0,
        "lost": False,
        "reply_lost": False,
        "recovery_pending": None,
        "recovery_interruptions": [],
        "recovery_disconnected": [],
        "recovery": RECOVERY_CASES.get(scenario, (None, None))[0],
        "loss_surface": RECOVERY_CASES.get(scenario, (None, None))[1],
        "publication_events": [],
        "merged": False,
        "errors": [],
    }
    if scenario == "legacy":
        state["posts"] = [
            {
                "id": 99,
                "body": "<!-- transist-review-reply -->\n"
                f"Reply to [this comment]({URL}#issuecomment-1): {REPLY}",
                "html_url": URL + "#issuecomment-99",
                "user": {"login": "fixture"},
                "surface": "conversation",
            }
        ]
    return state


def inspect_workspace(target: Path, fixture: dict) -> list[str]:
    """Inspect native Git stages and workspace files against finite deliverables."""
    allowed = {".gitignore", "README.md", "src/delivery.txt"}
    if fixture["workflow"] == "cursor_ticket_delivery":
        allowed.add("openspec/config.yaml")
        allowed.update(
            "openspec/changes/proj-123/" + name
            for name in (
                "proposal.md",
                "tasks.md",
                "design.md",
                "plan.md",
                "specs/delivery/spec.md",
            )
        )
    for staged in fixture["staged"]:
        require(
            set(filter(None, staged)) <= allowed, "operational file entered Git staging"
        )
    tracked = git(target, "ls-files").splitlines()
    require(set(tracked) <= allowed, "operational file entered a native Git commit")
    present = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(target).parts
    }
    require(
        present <= allowed, "operational file leaked into workspace even if ignored"
    )
    return tracked


def inspect_reply_recovery(driver: DeliveryDriver, name: str, fixture: dict) -> None:
    """Prove accepted/lost delivery is fetched and reconciled before any later POST."""
    require(
        fixture["reply_lost"], "selected lost-response publication was not exercised"
    )
    lost = fixture["lost_publication"]
    require(
        lost["surface"] == fixture["loss_surface"] and lost["response_lost"],
        "publication failed on the wrong selected surface",
    )
    events = fixture["publication_events"]
    matching_posts = [
        event
        for event in events
        if event["kind"] == "accepted_reply_post" and event["marker"] == lost["marker"]
    ]
    require(len(matching_posts) == 1, "accepted/lost reply was POSTed a second time")
    queries = [
        event
        for event in events
        if event["kind"] == "reply_collection_get"
        and event["sequence"] > lost["sequence"]
    ]
    require(
        {query["surface"] for query in queries} == {"conversation", "review_thread"},
        "re-entry did not query both complete remote reply surfaces",
    )
    matching_queries = [
        query
        for query in queries
        if query["surface"] == lost["surface"]
        and any(
            post["id"] == lost["id"]
            and post["body"] == lost["body"]
            and lost["marker"] in post["body"]
            for post in query["returned"]
        )
    ]
    require(
        bool(matching_queries),
        "re-entry never fetched the existing exact remote marker",
    )
    later_posts = [
        event
        for event in events
        if event["kind"] == "accepted_reply_post"
        and event["sequence"] > lost["sequence"]
    ]
    for post in later_posts:
        require(
            {
                query["surface"]
                for query in queries
                if query["sequence"] < post["sequence"]
            }
            == {"conversation", "review_thread"},
            "re-entry POST preceded complete reconciliation queries",
        )
    if lost["surface"] == "review_thread":
        require(
            not later_posts, "both thread-loss batch replies already existed remotely"
        )
    published = json.loads(
        driver.blob(name, driver.head(name, "review_replies_publish"))
    )
    comment = "R_thread" if lost["surface"] == "review_thread" else "C_pending"
    reconciled = [
        item for item in published["responses"] if item["comment_id"] == comment
    ]
    require(
        len(reconciled) == 1
        and reconciled[0]["status"] == "skipped"
        and reconciled[0]["reason"] == "remote_duplicate_reply",
        "real publisher did not report remote reconciliation",
    )
    fixture["recovery_proof"] = {
        "operation": fixture["recovery"],
        "loss_surface": fixture["loss_surface"],
        "lost_publication": lost,
        "queries_after_loss": queries,
        "posts_after_loss": later_posts,
        "reconciled_response": reconciled[0],
    }


def inspect_documents(
    driver: DeliveryDriver, name: str, scenario: str, fixture: dict
) -> list[dict]:
    """Assert exact committed bytes and decision scopes from actual runtime storage."""
    run_root = driver.home / "runs" / ("run_" + name)
    issue = json.loads(driver.blob(name, driver.head(name, "jira_issue")))
    require(
        issue.get("key") == "PROJ-123"
        or issue.get("issue", {}).get("key") == "PROJ-123",
        "wrong managed ticket bytes",
    )
    tree = json.loads(driver.blob(name, driver.head(name, "attachments")))
    members = {
        member: (run_root / "documents/blobs" / value["sha256"]).read_bytes()
        for member, value in tree["files"].items()
    }
    require(ATTACHMENT in members.values(), "exact attachment bytes were not retained")
    manifest = json.loads(members["manifest.json"])
    require(
        all(
            not Path(item["local_path"]).is_absolute()
            and ".." not in Path(item["local_path"]).parts
            for item in manifest["downloaded"]
        ),
        "attachment manifest contains staging paths",
    )
    projection = json.loads(driver.blob(name, driver.head(name, "attachment_context")))
    require(
        {member: base64.b64decode(raw) for member, raw in projection["members"].items()}
        == members,
        "model attachment projection changed member bytes",
    )
    header, *records = [
        json.loads(line)
        for line in driver.blob(
            name, driver.head(name, "reviewer_context")
        ).splitlines()
    ]
    require(header["root_run_id"] == name, "child replaced root identity")
    decisions = [
        json.loads(path.read_text()) for path in run_root.rglob("gates/history/*.json")
    ]
    for path in run_root.rglob(
        "step_executions/check_pr_exit_approvals/execution_*.json"
    ):
        execution = json.loads(path.read_text())
        for revision in execution.get("document_revisions", []):
            if revision["document"] == "pr_approvals":
                output = json.loads(driver.blob(name, revision))
                require(
                    output["approval_count"] in {0, 1},
                    "superseded/anonymous reviews inflated approvals",
                )
                require(
                    type(output["approval_ready"]) is bool,
                    "approval action returned a non-Boolean",
                )
                require(
                    output["approval_ready"] == (output["approval_count"] == 1),
                    "typed approval readiness changed decision rules",
                )

    def canonical(value: dict) -> str:
        """Compare complete immutable evidence independently of JSON formatting."""
        return json.dumps(value, sort_keys=True)

    retained = [value for value in decisions if value["decision"] != "rejected"]
    require(
        sorted(map(canonical, retained)) == sorted(map(canonical, records)),
        "a reviewer decision or its exact review scope was lost across modules",
    )
    if (
        fixture["agents"].get("review", 0)
        and fixture["workflow"] == "cursor_ticket_delivery"
    ):
        for step in (
            "prepare_pending_review_comments",
            "merge_pending_review_comments",
            "merge_pending_after_failed_validation",
            "filter_review_comments",
        ):
            for path in run_root.rglob(f"step_executions/{step}/execution_*.json"):
                execution = json.loads(path.read_text())
                for revision in execution.get("document_revisions", []):
                    if revision["document"] in {
                        "review_comments",
                        "review_comments_actionable",
                    }:
                        value = json.loads(driver.blob(name, revision))
                        for comment in value["comments"]:
                            if comment["id"] == "R_thread":
                                require(
                                    comment.get("line") is None
                                    and comment.get("original_line") is None,
                                    "numeric line bypassed header-only location",
                                )
                                require(
                                    comment.get("diff_hunk_header") == DIFF_HEADER
                                    and "diff_hunk" not in comment,
                                    "projected header was dropped or "
                                    "raw diff duplicated",
                                )
    if scenario == "reject":
        require(
            len(decisions) == 1 and decisions[0]["decision"] == "rejected",
            "terminal rejection was not preserved in authoritative history",
        )
        require(not fixture["staged"], "rejection dispatched a Git staging action")
    if scenario == "validation" and fixture["workflow"] == "hotfix_ticket_delivery":
        failed = [
            state["steps"]["implement_fix"]
            for state in driver.states(name)
            if "implement_fix" in state["steps"]
        ]
        require(
            len(failed) == 1 and failed[0]["status"] == "failed",
            "wrong failed-validation producer",
        )
        require(
            "document output validation failed" in json.dumps(failed[0]["last_result"]),
            "failure was not managed-output validation",
        )
        require(
            driver.head(name, "implementation_notes")["execution"] == 0,
            "failed output advanced notes revision",
        )
        require(
            not fixture["staged"] and not decisions,
            "invalid model output reached review or Git staging",
        )
    if scenario == "validation" and fixture["workflow"] == "cursor_ticket_delivery":
        require(
            fixture["agents"].get("verify", 0) >= 4,
            "validation/remediation/PR revalidation stages missing",
        )
        require(
            any(
                record["gate_id"] == "review-exit-after-failed-validation"
                and record["decision"] == "request_changes"
                for record in records
            ),
            "failed-validation override did not request remediation",
        )
    if scenario == "changes":
        requests = [
            value for value in records if value["decision"] == "request_changes"
        ]
        require(
            len(requests)
            >= (3 if fixture["workflow"] == "cursor_ticket_delivery" else 2),
            "request-change decisions missing across module boundaries",
        )
        # Inspect committed outputs of the POST-gate merge steps, not arbitrary
        # blobs that might include only the first raw fetch.
        requests_seen = []
        raw_after = []
        for step in (
            "merge_pending_review_comments",
            "merge_pending_after_failed_validation",
            "refresh_pr_comments",
            "refresh_pr_comments_after_failed_validation",
        ):
            for path in run_root.rglob(f"step_executions/{step}/execution_*.json"):
                execution = json.loads(path.read_text())
                for revision in execution.get("document_revisions", []):
                    value = json.loads(driver.blob(name, revision))
                    if revision["document"] == "review_comments":
                        requests_seen.extend(value["comments"])
                    elif revision["document"] == "review_comments_raw":
                        raw_after.extend(value["comments"])
        require(
            any(
                isinstance(value, dict)
                and value.get("id") == "C_pending"
                and value.get("body") == REQUEST
                for value in requests_seen
            ),
            "exact pre-gate pending request was not durably preserved",
        )
        require(
            not any(value.get("id") == "C_pending" for value in raw_after),
            "post-gate fixture did not advance beyond pending request",
        )
    if fixture["reply_lost"]:
        replies = [
            post for post in fixture["posts"] if "transist-review-reply" in post["body"]
        ]
        require(
            len(replies) == 2 and len({post["body"] for post in replies}) == 2,
            "ambiguous publication produced duplicate replies",
        )
        require(
            all("transist-review-publication:" in post["body"] for post in replies),
            "stable publication identity marker missing",
        )
    if (
        fixture["workflow"] == "cursor_ticket_delivery"
        and fixture["recovery"] is not None
    ):
        inspect_reply_recovery(driver, name, fixture)
    if "pr_body" in fixture:
        require(
            driver.blob(name, driver.head(name, "pr_body_for_open"))
            == fixture["pr_body"].encode(),
            "GitHub did not receive exact managed PR bytes",
        )
        require(
            fixture["pr_body"].startswith("Addresses: [PROJ-123]("),
            "managed PR header was lost",
        )
    if scenario == "legacy":
        require(len(fixture["posts"]) == 1, "legacy ambiguity posted another reply")
        failures = [
            step.get("last_result", {})
            for state in driver.states(name)
            for step in state["steps"].values()
            if step["status"] == "failed"
        ]
        require(
            any(
                "legacy reply has no exact publication identity" in json.dumps(result)
                for result in failures
            ),
            "failure was not legacy identity ambiguity",
        )
    for state in driver.states(name):
        publisher = state["steps"].get("publish_review_responses", {})
        if "last_request" in publisher:
            flag = publisher["last_request"]["input"]["resolve_addressed_threads"]
            require(type(flag) is bool, "publication flag became a string Boolean")
            committed = state["steps"]["commit_review_changes"]["last_result"][
                "output"
            ]["committed"]
            require(
                flag is committed,
                "publication flag did not use the actual commit result",
            )
    return [header, *records]


def isolation(
    driver: DeliveryDriver,
    reference: str,
    source: str,
    inputs: dict,
    server: object,
    example: str,
) -> None:
    """Execute independent run and real replay against one coordinated workspace."""
    before = driver.blob(source, driver.head(source, "reviewer_context"))
    for kind in ("independent", "replay"):
        server.fixture = fixture_state(example, kind)
        name = example + "_" + kind
        with driver.peers([server]):
            if kind == "replay":
                try:
                    driver.cli("runs", "replay", source, "--run-ref", name)
                finally:
                    if name not in driver.runs:
                        driver.runs.append(name)
            else:
                driver.start(reference, name, inputs)
            state = drive(driver, name, kind, server)
        require(
            state["status"] == "success", kind + " did not complete the actual graph"
        )
        require(
            state.get("cleanup", {}).get("state") == "succeeded",
            "fresh root cleanup failed",
        )
        inspect_workspace(Path(inputs["repo_path"]), server.fixture)
        head = driver.head(name, "reviewer_context")
        ledger = driver.blob(name, head)
        header = json.loads(ledger.splitlines()[0])
        require(
            header["root_run_id"] == name,
            "fresh run/replay reused root ledger identity",
        )
        require(head["root_run_id"] == name, "fresh namespace was not root-owned")
        require(
            before == driver.blob(source, driver.head(source, "reviewer_context")),
            "independent execution mutated source documents",
        )
        require(ledger != before, "replay or independent run reused old ledger bytes")
        (driver.root / (kind + "-observations.json")).write_text(
            json.dumps(
                {
                    "status": state["status"],
                    "head": head,
                    "ledger": ledger.decode(),
                    "provider": server.fixture,
                    "same_workspace": inputs["repo_path"],
                    "ticket": inputs["jira_ticket_id"],
                },
                indent=2,
            )
        )
        print(
            f"PASS {example} {kind}: fresh namespace/identity; "
            "same ticket and coordinated workspace",
            flush=True,
        )


def drive(
    driver: DeliveryDriver,
    name: str,
    scenario: str,
    server: object,
    progress: dict | None = None,
) -> dict:
    """Exercise actual human gates and bounded recovery without editing run state."""
    progress = {} if progress is None else progress
    changed: set[str] = progress.setdefault("changed", set())
    decided: set[tuple] = progress.setdefault("decided", set())
    for _ in range(30):
        progress["turns"] = progress.get("turns", 0) + 1
        if progress["turns"] > 30:
            raise ValueError("delivery fixture exceeded gate/recovery bound")
        state = driver.wait(name)
        if state["status"] == "success":
            driver.settle()
            return json.loads(driver.cli("runs", "show", name).stdout)
        if state["status"] == "failed":
            driver.settle()
            return state
        driver.settle()
        child, request = driver.gate(name)
        gate_id = request["gate_id"]
        require(
            request["review_documents"], "delivery gate has no exact document review"
        )
        decision = "approve"
        if scenario == "reject":
            decision = "reject"
        elif scenario == "changes" and gate_id not in changed:
            decision = "request-changes"
            changed.add(gate_id)
        elif (
            (server.fixture["recovery"] is not None or scenario == "legacy")
            and gate_id == "review-cycle-decision"
            and gate_id not in changed
        ):
            decision = "request-changes"
            changed.add(gate_id)
        elif (
            scenario == "validation"
            and gate_id == "review-exit-after-failed-validation"
        ):
            decision = "request-changes"
        identity = (
            child["run_id"],
            gate_id,
            request["execution"],
            tuple(item["revision_id"] for item in request["review_documents"]),
            decision,
        )
        require(
            identity not in decided,
            "approved consumer failed and reblocked the same review; "
            "inspect retained failure",
        )
        decided.add(identity)
        driver.cli(
            "runs",
            "gate",
            decision,
            name,
            gate_id,
            "--actor",
            "fixture-reviewer",
            "--reason",
            "  Exact synthetic scope\nKeep boundaries.  ",
        )
    raise ValueError("delivery fixture exceeded gate/recovery bound")


def record_provenance(driver: DeliveryDriver, plugins: Path, workflow: Path) -> None:
    """Record the real dirty source tuple and exact binary/selected payload identity."""
    receipt = {
        "sources": {},
        "binary_sha256": hashlib.sha256(driver.binary.read_bytes()).hexdigest(),
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "pythonpath_unset": "PYTHONPATH" not in os.environ,
        },
    }
    for label, checkout in (("workflows", ROOT), ("plugins", plugins)):
        receipt["sources"][label] = source_identity(checkout)
    receipt["payload_inventories"] = {
        path.name: json.loads(path.read_text())
        for path in driver.root.glob("*-payload.json")
    }
    receipt["plugin_dir_sha256"] = {}
    for manifest in sorted((driver.root / "dependencies").glob("*/plugin.yaml")):
        meta = yaml.safe_load(manifest.read_text())
        digest = hashlib.sha256()
        for relative in sorted({"plugin.yaml", *meta["package"]["files"]}):
            source = manifest.parent / relative
            installed = (
                driver.home / "plugins" / meta["id"] / meta["version"] / relative
            )
            require(
                source.read_bytes() == installed.read_bytes(),
                "installed selected bytes drifted",
            )
            require(
                source.stat().st_mode == installed.stat().st_mode,
                "installed selected mode drifted",
            )
            digest.update(relative.encode() + b"\0")
            digest.update(struct.pack("<I", source.stat().st_mode))
            digest.update(source.read_bytes() + b"\0")
        receipt["plugin_dir_sha256"][meta["id"]] = digest.hexdigest()
    reports = [
        driver.cli("workflows", "explain", "--path", str(workflow)).stdout
        for _ in range(2)
    ]
    require(reports[0] == reports[1], "delivery explanation changed between reads")
    explanation = json.loads(reports[0])
    projection = render(explanation)
    receipt["authored_assets"] = explanation["assets"]
    receipt["definition_sha256"] = explanation["definition_sha256"]
    receipt["explanation_sha256"] = hashlib.sha256(reports[0].encode()).hexdigest()
    receipt["projection_sha256"] = hashlib.sha256(projection.encode()).hexdigest()
    expected = json.loads((workflow.parent / "explanation.snapshot.json").read_text())
    require(
        expected["definition_sha256"] == receipt["definition_sha256"]
        and expected["projection_sha256"] == receipt["projection_sha256"],
        "delivery source differs from generated explanation snapshot",
    )
    (driver.root / "explanation.json").write_text(reports[0])
    (driver.root / "explanation.txt").write_text(projection)
    (driver.root / "source-provenance.json").write_text(json.dumps(receipt, indent=2))


def _run_scenario(
    driver: DeliveryDriver,
    reference: str,
    name: str,
    inputs: dict,
    scenario: str,
    server: object,
) -> dict:
    """Recover proved canceled work in fresh source-verified native peer scopes."""
    interruptions = 0
    progress: dict = {}
    while True:
        try:
            with driver.peers([server]):
                if interruptions == 0:
                    driver.start(reference, name, inputs)
                else:
                    driver.cli("runs", server.fixture["recovery"], name)
                return drive(driver, name, scenario, server, progress)
        except _RecoveryBoundary:
            interruptions += 1
            require(
                server.fixture["recovery"] in {"retry", "resume"}
                and interruptions <= 2,
                "delivery recovery interruption budget exceeded",
            )
            receipt = json.loads(
                (
                    driver.root / f"namespace-peers-{driver.transport_sequence}.json"
                ).read_text()
            )
            require(
                receipt["cleanup_confirmed"]
                and not receipt["owned_live_processes"]
                and receipt["error"] is None
                and not receipt["cleanup_errors"]
                and receipt["caller_namespace_unchanged"]
                and receipt["helper_sha256"] == driver.peer_helper.sha256
                and receipt["controller_source_sha256"] == driver.peer_helper.sha256
                and receipt["supervisor_source_sha256s"] == [driver.peer_helper.sha256]
                and receipt["native_cleanup_reports"]
                and all(
                    report["source_sha256"] == driver.peer_helper.sha256
                    and not report["ownership_uncertain"]
                    and not report["remaining"]
                    for report in receipt["native_cleanup_reports"]
                )
                and all(
                    not receipt[key]
                    for key in (
                        "handlers_remaining",
                        "listeners_remaining",
                        "namespace_fds_remaining",
                        "pidfds_remaining",
                        "control_fds_remaining",
                        "source_fds_remaining",
                        "pending_jobs",
                        "controller_alive",
                    )
                ),
                "interrupted scope lacks exact-source owned cleanup proof",
            )
            record = server.fixture["recovery_interruptions"][-1]
            require(
                record["stage"] in server.fixture["recovery_disconnected"],
                "canceled fake request did not disconnect",
            )
            record["native_cleanup_confirmed"] = True


def _failure_cleanup_contract(
    driver: DeliveryDriver,
    reference: str,
    inputs: dict,
    server: object,
    example: str,
    original: dict,
) -> None:
    """Prove both primary recovery verbs refuse real authored failed cleanup."""
    target = driver.workspace / "post-cleanup"
    workspace(target, example == "cursor_ticket_delivery")
    server.fixture = fixture_state(example, "failure_cleanup")
    driver.fixture = server.fixture
    name = example + "_post_cleanup"
    inputs = dict(inputs, repo_path=str(target))
    with driver.peers([server]):
        failed = driver.start(reference, name, inputs)
        require(failed["status"] == "failed", "failure control did not fail")
        cleanup = failed.get("cleanup", {})
        required = {
            step["id"] for step in original["cleanup"] if "failed" in step["when"]
        }
        counts = {
            key: value["executions"] for key, value in cleanup.get("steps", {}).items()
        }
        require(
            cleanup.get("trigger") == "failed"
            and cleanup.get("state") == "succeeded"
            and set(counts) == required
            and all(value == 1 for value in counts.values()),
            "authored failure cleanup was not executed exactly once",
        )
        executions = {
            key: value["executions"] for key, value in failed["steps"].items()
        }
        request_count = len(server.fixture["requests"])
        operations = []
        for operation in ("retry", "resume"):
            result = driver.cli("runs", operation, name, ok=False)
            refused = driver.wait(name)
            require(
                refused["status"] == "failed"
                and {
                    key: value["executions"] for key, value in refused["steps"].items()
                }
                == executions
                and {
                    key: value["executions"]
                    for key, value in refused["cleanup"]["steps"].items()
                }
                == counts
                and len(server.fixture["requests"]) == request_count,
                "primary recovery redispatched after failure cleanup",
            )
            require(
                "explicit cleanup has begun"
                in (driver.home / "runs" / ("run_" + name) / "runner.log").read_text(),
                "missing runtime cleanup refusal",
            )
            operations.append(
                {
                    "operation": operation,
                    "cli_exit": result.returncode,
                    "status": refused["status"],
                    "extra_provider_calls": 0,
                }
            )
    (driver.root / "post-cleanup-observations.json").write_text(
        json.dumps(
            {"run": name, "cleanup_executions": counts, "operations": operations},
            indent=2,
        )
    )
    print(
        f"PASS {example} failure cleanup blocks retry/resume; zero redispatch",
        flush=True,
    )


def run(
    binary: Path,
    plugins: Path,
    base: Path,
    example: str,
    *,
    scenarios: tuple[str, ...] | None = None,
) -> None:
    """Install the complete selected payload and execute both real delivery graphs."""
    driver = DeliveryDriver(binary, plugins, base, example)
    original_path = ROOT / "examples" / example / "workflow.yaml"
    original = yaml.safe_load(original_path.read_text())
    required = required_scenarios(example)
    selected = required if scenarios is None else scenarios
    require(
        bool(selected) and set(selected) <= set(required),
        "invalid delivery scenario selection",
    )
    try:
        with service(example) as server:
            fake = driver.root / "bin"
            fake.mkdir()
            for name in ("git", "gh", "copilot", "cursor-agent", "openspec"):
                path = fake / name
                path.write_text(
                    f"#!{fixture_python()}\nBASE={server.base_url!r}\n"
                    "REAL_GIT='/usr/bin/git'\n" + PEER
                )
                path.chmod(0o755)
            driver.env.update(
                PATH=str(fake) + os.pathsep + driver.env["PATH"],
                CURSOR_AGENT_PATH=str(fake / "cursor-agent"),
                JIRA_AUTH_HEADER="dummy-jira-fixture",
            )
            if sys.platform == "linux":
                expose_native_awk(fake, driver.env)
            config_path = driver.home / "config.yaml"
            config = yaml.safe_load(config_path.read_text())
            config["policy"]["child_env"] = {
                "inherit": False,
                "allowlist": ["PATH", "CURSOR_AGENT_PATH"],
            }
            config_path.write_text(yaml.safe_dump(config))
            driver.install_plugins(original_path)
            record_provenance(driver, plugins, original_path)
            for directory in ("modules", "prompts", "scripts"):
                shutil.copytree(
                    original_path.parent / directory,
                    driver.source / directory,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            flow = copy.deepcopy(original)
            flow["network"] = local_network(server.server_port)
            reference = driver.install_flow(flow, example + "_fixture")
            receipts = []
            for scenario in selected:
                target = driver.workspace / scenario
                workspace(target, example == "cursor_ticket_delivery")
                server.fixture = fixture_state(example, scenario)
                driver.fixture = server.fixture
                inputs = {
                    "repo_path": str(target),
                    "jira_ticket_id": "PROJ-123",
                    "jira_site_url": server.base_url,
                    "trunk_branch": "main",
                }
                name = example + "_" + scenario
                state = _run_scenario(driver, reference, name, inputs, scenario, server)
                if server.fixture["recovery"] is not None:
                    require(
                        [
                            item["stage"]
                            for item in server.fixture["recovery_interruptions"]
                        ]
                        == ["jira_fetch", "reply"],
                        "both required response-loss recovery boundaries "
                        "were not exercised",
                    )
                expected = (
                    "failed"
                    if scenario in {"reject", "legacy"}
                    or (
                        scenario == "validation" and example == "hotfix_ticket_delivery"
                    )
                    else "success"
                )
                require(
                    state["status"] == expected,
                    f"{example} {scenario} status {state['status']} != {expected}",
                )
                if expected == "success":
                    require(
                        state.get("cleanup", {}).get("state") == "succeeded",
                        "success cleanup did not execute the authored root actions",
                    )
                    require(
                        git(target, "branch", "--show-current").strip() == "main",
                        "root cleanup did not restore trunk",
                    )
                    require(
                        (target / "src/delivery.txt").is_file(),
                        "simulated merge lost the actual committed source deliverable",
                    )
                require(not server.fixture["errors"], "fake provider assertions failed")
                header, *records = inspect_documents(
                    driver, name, scenario, server.fixture
                )
                require(
                    header["root_run_id"] == name,
                    "root ledger identity changed in child",
                )
                require(
                    len(
                        {
                            (
                                r["run_id"],
                                r["gate_id"],
                                r["step_id"],
                                r["decided_at_ms"],
                            )
                            for r in records
                        }
                    )
                    == len(records),
                    "duplicate reviewer decisions",
                )
                tracked = inspect_workspace(target, server.fixture)
                observation = {
                    "scenario": scenario,
                    "status": state["status"],
                    "ledger": [header, *records],
                    "provider": server.fixture,
                    "tracked": tracked,
                }
                (driver.root / (scenario + "-observations.json")).write_text(
                    json.dumps(observation, indent=2)
                )
                receipts.append(
                    {
                        "scenario": scenario,
                        "status": state["status"],
                        "decisions": len(records),
                        "recovery": server.fixture["recovery"],
                        "loss_surface": server.fixture["loss_surface"],
                        "publication_recovery": server.fixture.get("recovery_proof"),
                    }
                )
                (driver.root / "receipt.json").write_text(
                    json.dumps(
                        {
                            "required": required,
                            "selected": selected,
                            "completed": receipts,
                            "complete": len(receipts) == len(required)
                            and set(selected) == set(required),
                        },
                        indent=2,
                    )
                )
                print(
                    f"PASS {example} {scenario}: {state['status']}, "
                    f"{len(records)} ledger records",
                    flush=True,
                )
                if scenario == "success":
                    isolation(driver, reference, name, inputs, server, example)
                    _failure_cleanup_contract(
                        driver, reference, inputs, server, example, original
                    )
    except Exception:
        (driver.root / "failure.txt").write_text(traceback.format_exc())
        if "server" in locals():
            (driver.root / "failure-provider.json").write_text(
                json.dumps(server.fixture, indent=2)
            )
        raise
    finally:
        driver.close()
        if "server" in locals():
            (driver.root / "provider-endpoint.json").write_text(
                json.dumps(
                    {
                        "url": server.base_url,
                        "requests": server.request_count,
                        "listener_settled": server.settled,
                    },
                    indent=2,
                )
            )
