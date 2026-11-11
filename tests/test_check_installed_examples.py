"""Installed inventory and prerequisite regressions, without provider execution."""

import contextlib
import io
import copy
import errno
import hashlib
import json
import socket
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_installed_examples as checker  # noqa: E402
import installed_delivery as delivery  # noqa: E402
from installed_delivery import (  # noqa: E402
    INSTRUCTION_SOURCE,
    Service,
    expose_native_awk,
    fixture_state,
    required_scenarios,
)


class InstalledCheckerTests(unittest.TestCase):
    """Every finite inventory entry runs; missing prerequisites never skip."""

    def test_changes_preserves_requests_until_the_authored_review_scan(self) -> None:
        """Only the post-review iteration can require the real scanner's context."""
        handler = object.__new__(Service)
        fixture = fixture_state("cursor_ticket_delivery", "changes")
        handler.server = Mock(fixture=fixture)
        prompt = '{"root_run_id":"fixture-review-scan"}'
        first = handler.agent({"args": ["-p", prompt]})
        self.assertTrue(
            first["write_files"]["src/delivery.txt"].startswith(INSTRUCTION_SOURCE)
        )
        with self.assertRaisesRegex(checker.CheckError, "real scanner's located"):
            handler.agent({"args": ["-p", prompt]})
        fixture["agents"]["implement"] = 1
        second = handler.agent(
            {"args": ["-p", prompt + "\nsrc/delivery.txt:1: hash-request"]}
        )
        self.assertNotIn("tst:", second["write_files"]["src/delivery.txt"])

    def test_recovery_eligibility_does_not_ignore_cleanup_or_missing_proof(
        self,
    ) -> None:
        """Only known unstarted cleanup states permit synthetic recovery."""
        for cleanup, allowed in (
            (None, True),
            ({"state": "skipped", "steps": {}}, True),
            ({}, False),
            ({"state": "skipped"}, False),
            ({"state": "skipped", "steps": {"owned": {}}}, False),
            ({"state": "succeeded", "steps": {}}, False),
            ({"state": "running", "steps": {}}, False),
            ({"state": "failed", "steps": {}}, False),
        ):
            with self.subTest(cleanup=cleanup):
                self.assertEqual(
                    delivery._cleanup_not_started({"cleanup": cleanup}), allowed
                )
        pending = {"trigger": "canceled", "state": "pending", "steps": {}}
        for status, recovery, changes, allowed in (
            ("running", None, {}, True),
            ("blocked", "recoverable", {}, True),
            ("canceled", None, {}, False),
            ("failed", None, {}, False),
            ("running", "cleanup_required", {}, False),
            ("running", "cleanup_completed", {}, False),
            ("running", "unknown", {}, False),
            ("running", None, {"trigger": "failed"}, False),
            ("running", None, {"started_at_ms": 1}, False),
            ("running", None, {"finished_at_ms": 1}, False),
            ("running", None, {"preflight": {"status": "passed"}}, False),
        ):
            with self.subTest(status=status, recovery=recovery, changes=changes):
                self.assertEqual(
                    delivery._cleanup_not_started(
                        {
                            "status": status,
                            "resume_count": 1,
                            "recovery_state": recovery,
                            "cleanup": dict(pending, **changes),
                        }
                    ),
                    allowed,
                )
        unrecovered = {"status": "running", "resume_count": 0, "cleanup": pending}
        self.assertFalse(delivery._cleanup_not_started(unrecovered))

    def test_response_barrier_requires_real_client_eof(self) -> None:
        """Withhold the response until the owning fake client actually disconnects."""
        handler = object.__new__(Service)
        fixture = fixture_state("cursor_ticket_delivery", "retry")
        handler.server = Mock(fixture=fixture)
        reader, writer = socket.socketpair()
        handler.connection = reader
        errors = []

        def serve() -> None:
            """Retain a worker failure rather than letting a thread hide it."""
            try:
                handler.wait_for_cancellation("jira_fetch")
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=serve)
        worker.start()
        try:
            deadline = time.monotonic() + 2
            while fixture["recovery_pending"] is None:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.001)
            self.assertEqual(fixture["recovery_disconnected"], [])
            self.assertTrue(worker.is_alive())
            writer.close()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(fixture["recovery_disconnected"], ["jira_fetch"])
        finally:
            writer.close()
            worker.join(2)
            reader.close()

    def test_recovery_barrier_accepts_only_live_eligible_parent_state(self) -> None:
        """A blocked parent can own active child work, but an idle gate cannot."""
        for status, live, cleanup, allowed in (
            ("running", True, None, True),
            ("blocked", True, None, True),
            ("blocked", False, None, False),
            ("failed", True, None, False),
            ("canceled", True, None, False),
            ("blocked", True, {"state": "succeeded", "steps": {}}, False),
        ):
            with self.subTest(status=status, live=live, cleanup=cleanup):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    path = root / "state.json"
                    path.write_text(
                        json.dumps(
                            {
                                "status": "canceled",
                                "cleanup": {
                                    "state": "skipped",
                                    "trigger": "canceled",
                                    "steps": {},
                                },
                            }
                        )
                    )
                    driver = object.__new__(delivery.DeliveryDriver)
                    driver.root, driver.transport_sequence = root, 1
                    driver.fixture = fixture_state("cursor_ticket_delivery", "retry")
                    driver.fixture["recovery_pending"] = "reply"
                    driver.cli = Mock()
                    driver.running = Mock(side_effect=[live, False])
                    before = {"status": status, "cleanup": cleanup}
                    if allowed:
                        driver.cancel_for_recovery("fixture", before, path)
                        driver.cli.assert_called_once_with("runs", "cancel", "fixture")
                        self.assertIsNone(driver.fixture["recovery_pending"])
                    else:
                        with self.assertRaisesRegex(checker.CheckError, "eligible"):
                            driver.cancel_for_recovery("fixture", before, path)
                        driver.cli.assert_not_called()

    def test_response_barrier_timeout_never_claims_disconnection(self) -> None:
        """An unobserved client remains a failure, not an eligible recovery receipt."""
        handler = object.__new__(Service)
        fixture = fixture_state("cursor_ticket_delivery", "resume")
        handler.server = Mock(fixture=fixture)
        with patch.object(
            delivery.time, "monotonic", side_effect=[0, 31]
        ), patch.object(delivery.select, "select") as select_call:
            with self.assertRaisesRegex(checker.CheckError, "did not disconnect"):
                handler.wait_for_cancellation("reply")
        self.assertEqual(fixture["recovery_disconnected"], [])
        select_call.assert_not_called()

    def test_interrupted_scope_uncertainty_is_not_swallowed_as_recovery(self) -> None:
        """The control-flow boundary cannot hide uncertain native teardown."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = {
                "cleanup_confirmed": True,
                "owned_live_processes": [],
                "error": None,
                "cleanup_errors": [],
                "caller_namespace_unchanged": True,
                "helper_sha256": "captured",
                "controller_source_sha256": "captured",
                "supervisor_source_sha256s": ["captured"],
                "native_cleanup_reports": [
                    {
                        "source_sha256": "captured",
                        "ownership_uncertain": False,
                        "remaining": [],
                    }
                ],
                **{
                    key: 0
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
                },
            }
            for mutation in (
                {"cleanup_confirmed": False},
                {
                    "native_cleanup_reports": [
                        {
                            "source_sha256": "captured",
                            "ownership_uncertain": True,
                            "remaining": [],
                        }
                    ]
                },
                {"pending_jobs": 1},
                {"controller_source_sha256": "other"},
            ):
                with self.subTest(mutation=mutation):
                    (root / "namespace-peers-1.json").write_text(
                        json.dumps(dict(receipt, **mutation))
                    )
                    driver = Mock(
                        root=root,
                        transport_sequence=1,
                        peer_helper=Mock(sha256="captured"),
                    )
                    driver.peers.return_value = contextlib.nullcontext()
                    driver.start.side_effect = delivery._RecoveryBoundary()
                    server = Mock(
                        fixture=fixture_state("cursor_ticket_delivery", "retry")
                    )
                    with self.assertRaisesRegex(checker.CheckError, "cleanup proof"):
                        delivery._run_scenario(
                            driver, "fixture", "run", {}, "retry", server
                        )
                    driver.cli.assert_not_called()

    def test_recovery_does_not_reset_the_total_gate_budget(self) -> None:
        """A peer-scope transition retains the original thirty-turn driving bound."""
        progress = {"turns": 29}
        driver = Mock()
        driver.wait.side_effect = delivery._RecoveryBoundary()
        with self.assertRaises(delivery._RecoveryBoundary):
            delivery.drive(driver, "fixture", "retry", Mock(), progress)
        self.assertEqual(progress["turns"], 30)
        with self.assertRaisesRegex(ValueError, "gate/recovery bound"):
            delivery.drive(driver, "fixture", "retry", Mock(), progress)
        self.assertEqual(driver.wait.call_count, 1)
        driver.cli.assert_not_called()

    def test_fixture_shebang_resolves_virtualenv_symlink(self) -> None:
        """Namespace-visible shebangs name real Python, not an unmounted venv alias."""
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / "python"
            native = Path(sys.executable).resolve(strict=True)
            alias.symlink_to(native)
            with patch.object(sys, "executable", str(alias)):
                self.assertEqual(checker.fixture_python(), native)
            alias.unlink()
            with patch.object(sys, "executable", str(alias)):
                with self.assertRaises(FileNotFoundError):
                    checker.fixture_python()

    def test_exact_public_runtime_and_admin_versions(self) -> None:
        """Both probes reject old, malformed, extra and unsuccessful output."""
        for identity in ("transist", "transist-admin"):
            for version, code, accepted in (
                ("0.1.1", 0, True),
                ("0.1.0", 0, False),
                ("0.12.0", 0, False),
                ("0.1.0-extra", 0, False),
                ("0.1.0\nextra", 0, False),
                ("invalid", 0, False),
                ("0.1.0", 1, False),
                ("0.1.1-extra", 0, False),
                ("0.1.1\nextra", 0, False),
                ("0.1.1", 1, False),
            ):
                with self.subTest(identity=identity, version=version, code=code):
                    result = Mock(
                        returncode=code, stdout=f"{identity} {version}\n".encode()
                    )
                    with patch.object(checker.subprocess, "run", return_value=result):
                        if accepted:
                            checker.executable(Path("/bin/sh"), identity)
                        else:
                            with self.assertRaises(checker.CheckError):
                                checker.executable(Path("/bin/sh"), identity)

    def test_inventory_and_repeatable_selection(self) -> None:
        """Both introductory examples run once; all four maintained roots are named."""
        self.assertEqual(
            set(checker.INVENTORY),
            {
                "edge_fault_advisory",
                "ai_agent_plugins_canary",
                "cursor_ticket_delivery",
                "hotfix_ticket_delivery",
            },
        )
        self.assertEqual(
            checker.select(["edge_fault_advisory"] * 2), ["edge_fault_advisory"]
        )
        self.assertEqual(checker.select([]), list(checker.INVENTORY))
        self.assertEqual(
            checker.select(["cursor_ticket_delivery"] * 2), ["cursor_ticket_delivery"]
        )
        self.assertEqual(
            checker.select(["hotfix_ticket_delivery"]), ["hotfix_ticket_delivery"]
        )
        self.assertTrue(all(checker.INVENTORY.values()))
        with self.assertRaises(checker.CheckError):
            checker.select(["unmaintained"])

    def test_missing_binary_fails_not_skips(self) -> None:
        """A nonexistent runtime fails even when the inventory is otherwise valid."""
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(
                checker.main(
                    [
                        "--transist",
                        str(Path(directory) / "missing"),
                        "--admin-bin",
                        "/bin/sh",
                        "--plugins-dir",
                        directory,
                        "--home-base",
                        directory,
                        "--example",
                        "edge_fault_advisory",
                    ]
                ),
                1,
            )

    def test_failure_diagnostic_retains_errno_and_stack_without_payloads(self) -> None:
        """Unexpected OS failures remain actionable without exception/local secrets."""
        marker = "synthetic-sensitive-payload"

        def failed_edge(*_args: object) -> None:
            error = OSError(errno.EINVAL, marker, "/private/" + marker)
            error.fixture_process_observation = {
                "child_pid": 42,
                "status_pid": 42,
                "status_tgid": 41,
                "observed_birth": None,
                "parent_birth": marker,
                "unexpected_payload": marker,
            }
            raise error

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = [
                "--transist",
                "/bin/sh",
                "--admin-bin",
                "/bin/sh",
                "--plugins-dir",
                directory,
                "--fixture-base",
                directory,
                "--example",
                "edge_fault_advisory",
            ]
            output = io.StringIO()
            with patch.object(
                checker, "executable", return_value=Path("/bin/sh")
            ), patch.object(
                checker, "edge", side_effect=failed_edge
            ), contextlib.redirect_stderr(
                output
            ):
                self.assertEqual(checker.main(args), 1)
                self.assertEqual(checker.main(args), 1)
            receipts = list(root.glob("installed-failure-*.json"))
            self.assertEqual(len(receipts), 2, "never overwrite an earlier failure")
            for receipt in receipts:
                raw = receipt.read_text()
                record = json.loads(raw)
                self.assertEqual(record["error_type"], "OSError")
                self.assertEqual(record["errno"], errno.EINVAL)
                self.assertEqual(
                    record["process_observation"],
                    {
                        "child_pid": 42,
                        "status_pid": 42,
                        "status_tgid": 41,
                        "observed_birth": None,
                    },
                )
                self.assertEqual(record["traceback"][-1]["function"], "failed_edge")
                self.assertEqual(record["traceback"][-1]["file"], Path(__file__).name)
                self.assertGreater(record["traceback"][-1]["line"], 0)
                self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(marker, raw)
                self.assertNotIn("/private/", raw)
            self.assertNotIn(marker, output.getvalue())
            self.assertIn("Installed examples incomplete: OSError", output.getvalue())

    def test_failure_diagnostic_write_error_preserves_nonzero_sanitized_result(
        self,
    ) -> None:
        """A full or unwritable evidence directory cannot hide the original failure."""
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(
                checker, "executable", side_effect=RuntimeError("secret-original")
            ), patch.object(
                checker,
                "record_failure",
                side_effect=PermissionError(errno.EACCES, "secret-diagnostic"),
            ), contextlib.redirect_stderr(
                output
            ):
                self.assertEqual(
                    checker.main(
                        [
                            "--transist",
                            "/bin/sh",
                            "--admin-bin",
                            "/bin/sh",
                            "--plugins-dir",
                            directory,
                            "--fixture-base",
                            directory,
                        ]
                    ),
                    1,
                )
            self.assertIn("Failure diagnostic could not be retained", output.getvalue())
            self.assertIn(
                "Installed examples incomplete: RuntimeError", output.getvalue()
            )
            self.assertNotIn("secret-", output.getvalue())

    def test_cleanup_wrapper_keeps_original_errno_and_numeric_observation(self) -> None:
        """Cleanup causes/contexts retain primary failures without sensitive strings."""
        with tempfile.TemporaryDirectory() as directory:
            original = OSError(errno.EINVAL, "synthetic-secret-original")
            original.fixture_process_observation = {"child_pid": 42, "status_tgid": 41}
            try:
                try:
                    raise original
                except OSError:
                    raise RuntimeError("synthetic-secret-cleanup") from RuntimeError(
                        "synthetic-secret-supervisor"
                    )
            except RuntimeError as error:
                # A cycle must not loop or duplicate the original failure.
                original.__context__ = error
                receipt = checker.record_failure(error, Path(directory))
            raw = receipt.read_text()
            record = json.loads(raw)
            self.assertEqual(record["error_type"], "RuntimeError")
            self.assertEqual(len(record["related_exceptions"]), 2)
            primary = next(
                item
                for item in record["related_exceptions"]
                if item["error_type"] == "OSError"
            )
            self.assertEqual(primary["errno"], errno.EINVAL)
            self.assertEqual(primary["process_observation"]["child_pid"], 42)
            self.assertTrue(primary["traceback"])
            self.assertNotIn("synthetic-secret-", raw)

    def test_delivery_default_inventory_requires_both_recovery_surfaces(self) -> None:
        """All four operation/surface combinations belong to the default full graph."""
        expected = {
            "retry": ("retry", "conversation"),
            "resume": ("resume", "conversation"),
            "retry_review_thread": ("retry", "review_thread"),
            "resume_review_thread": ("resume", "review_thread"),
        }
        cursor = required_scenarios("cursor_ticket_delivery")
        self.assertEqual(len(cursor), 9)
        self.assertEqual(len(set(cursor)), len(cursor))
        self.assertLessEqual(set(expected), set(cursor))
        for scenario, (operation, surface) in expected.items():
            state = fixture_state("cursor_ticket_delivery", scenario)
            self.assertEqual(
                (state["recovery"], state["loss_surface"]), (operation, surface)
            )
            self.assertFalse(state["reply_lost"])
            self.assertEqual(state["publication_events"], [])
        self.assertEqual(
            required_scenarios("hotfix_ticket_delivery"),
            ("reject", "validation", "success", "changes", "retry", "resume"),
        )

    def test_repository_arguments_and_no_unfiltered_false_pass(self) -> None:
        """Unfiltered dispatch includes all four; required-runner failures propagate."""
        with tempfile.TemporaryDirectory() as directory:
            args = [
                "--transist",
                "/bin/sh",
                "--admin-bin",
                "/bin/sh",
                "--plugins-dir",
                directory,
                "--home-base",
                directory,
            ]
            with patch.object(
                checker, "executable", return_value=Path("/bin/sh")
            ), patch.object(checker, "edge") as edge, patch.object(
                checker, "canary"
            ) as canary, patch(
                "installed_delivery.run"
            ) as delivery, contextlib.redirect_stdout(
                io.StringIO()
            ), contextlib.redirect_stderr(
                io.StringIO()
            ), patch(
                "check_authoring_fixtures.run_all"
            ) as authoring:
                self.assertEqual(
                    checker.main(args + ["--example", "edge_fault_advisory"] * 2), 0
                )
                edge.assert_called_once()
                authoring.assert_not_called()
                self.assertEqual(checker.main(args), 0)
                authoring.assert_called_once()
                self.assertEqual(edge.call_count, 2)
                canary.assert_called_once()
                self.assertEqual(
                    [call.args[-1] for call in delivery.call_args_list],
                    ["cursor_ticket_delivery", "hotfix_ticket_delivery"],
                )
                delivery.side_effect = checker.CheckError("required fixture failed")
                self.assertEqual(
                    checker.main(args + ["--example", "cursor_ticket_delivery"]), 1
                )
                delivery.side_effect = None
                authoring.side_effect = checker.CheckError("authoring fixture failed")
                self.assertEqual(checker.main(args), 1)

    def test_linux_tool_grant_is_exact_and_never_mutates_authored_flow(self) -> None:
        """Only the external fake-bin read grant is added; Git/workspace stay exact."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            driver = checker.Driver.__new__(checker.Driver)
            driver.root = root
            driver.source = root / "source"
            driver.source.mkdir()
            driver.cli = Mock()
            original = {
                "id": "authored",
                "workspace": {"path": "{{inputs.repo_path}}", "access": "read_only"},
                "network": {"mode": "none"},
                "filesystem_policy": {"write_allow_paths": ["~/.cursor"]},
                "steps": [{"id": "unchanged", "uses": "process:shell/read_file"}],
            }
            before = copy.deepcopy(original)
            for platform in ("linux", "darwin"):
                with patch.object(checker.sys, "platform", platform):
                    driver.install_flow(original, platform)
                actual = checker.yaml.safe_load(
                    (driver.source / (platform + ".yaml")).read_text()
                )
                expected = copy.deepcopy(before)
                expected["id"] = platform
                if platform == "linux":
                    expected["filesystem_policy"]["read_allow_paths"] = [
                        str(root / "bin")
                    ]
                self.assertEqual(actual, expected)
                self.assertEqual(original, before)

    def test_peer_scope_routes_cli_and_settles_before_transport_release(self) -> None:
        """The actual CLI wrapper delegates, then closes owned runs before peers."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            driver = checker.Driver.__new__(checker.Driver)
            driver.root = root
            driver.home = root / "home"
            driver.home.mkdir()
            (driver.home / "config.yaml").write_text("policy: {}\n")
            driver.plugins = root / "checkout"
            (driver.plugins / "tests").mkdir(parents=True)
            (driver.plugins / "tests/namespace_peers.py").write_text("# fixture\n")
            driver.binary = Path("/fixture/transist")
            driver.workspace = root
            driver.sequence = driver.transport_sequence = 0
            driver.transport = None
            driver.env = {"PATH": "/fixture/original"}
            events = []
            driver.close = lambda: events.append("settle")
            transport = Mock()
            transport.environment.side_effect = lambda env: {**env, "PATH": "shim"}
            transport.run.return_value = checker.subprocess.CompletedProcess(
                [], 0, "{}", ""
            )
            scope = Mock()
            scope.__enter__ = Mock(return_value=transport)
            scope.__exit__ = Mock(side_effect=lambda *_args: events.append("release"))
            helper = driver.plugins / "tests/namespace_peers.py"
            driver.peer_helper = checker.PeerHelper(
                helper,
                hashlib.sha256(helper.read_bytes()).hexdigest(),
                Mock(return_value=scope),
                helper.read_bytes(),
            )
            with self.assertRaisesRegex(ValueError, "fixture failure"):
                with driver.peers([]):
                    driver.cli("workflows", "explain", "--path", "source.yaml")
                    raise ValueError("fixture failure")
            transport.run.assert_called_once()
            self.assertEqual(events, ["settle", "release"])
            self.assertIsNone(driver.transport)
            self.assertEqual(driver.env, {"PATH": "/fixture/original"})
            settings = checker.yaml.safe_load((driver.home / "config.yaml").read_text())
            self.assertEqual(settings["policy"]["child_env"]["allowlist"], ["PATH"])

    def test_missing_explicit_peer_helper_fails_closed(self) -> None:
        """Missing explicit helpers cannot fall back to host networking/imports."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(checker.CheckError):
                checker.peer_controller(Path(directory))

    def test_native_awk_alias_executes_exact_real_tool_and_requires_it(self) -> None:
        """A mounted tool alias preserves real awk behavior, not a canned response."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            tools = root / "tools"
            tools.mkdir()
            with self.assertRaisesRegex(checker.CheckError, "real native awk"):
                expose_native_awk(tools, {"PATH": ""})
            expose_native_awk(tools, {"PATH": checker.os.defpath})
            native = (tools / "awk").resolve()
            record = json.loads((root / "native-tools.json").read_text())["awk"]
            self.assertEqual(record["resolved"], str(native))
            self.assertEqual(
                record["sha256"], hashlib.sha256(native.read_bytes()).hexdigest()
            )
            result = checker.subprocess.run(
                [str(tools / "awk"), "BEGIN { print 3 + 4 }"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout, "7\n")


class PeerHelperIdentityTests(unittest.TestCase):
    """Real source mutations cannot make loaded code claim another byte identity."""

    def setUp(self) -> None:
        """Create one explicit checkout and Python source, without plugin execution."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.checkout = self.root / "selected"
        (self.checkout / "tests").mkdir(parents=True)
        self.path = self.checkout / "tests/namespace_peers.py"
        self.executed = self.root / "executed"
        self.source_a = self.source("A")
        self.source_b = self.source("B")
        self.path.write_bytes(self.source_a)

    def source(self, label: str) -> bytes:
        """Build distinct real dataclass helpers recording executed code and calls."""
        return (
            "from __future__ import annotations\n"
            "from dataclasses import dataclass\n"
            "from pathlib import Path\n"
            "import hashlib\n"
            "import subprocess\n"
            "from typing import ClassVar\n"
            "SOURCE_BYTES = globals()['__namespace_peers_source__']\n"
            "HELPER_SHA256 = hashlib.sha256(SOURCE_BYTES).hexdigest()\n"
            "assert HELPER_SHA256 == globals()['__namespace_peers_expected_sha256__']\n"
            f"Path({str(self.executed)!r}).write_text({label!r})\n"
            "@dataclass\n"
            "class NamespacePeers:\n"
            "    peers: list\n"
            "    tools: Path\n"
            "    roots: list[Path]\n"
            "    receipt: Path\n"
            f"    implementation: ClassVar[str] = {label!r}\n"
            "    calls: ClassVar[list[str]] = []\n"
            "    def __enter__(self) -> NamespacePeers:\n"
            "        self.calls.append('enter')\n"
            "        return self\n"
            "    def environment(self, env: dict) -> dict:\n"
            "        return dict(env)\n"
            "    def run(self, argv: list, **kwargs: object) -> object:\n"
            "        self.calls.append('run')\n"
            "        return subprocess.CompletedProcess(argv, 0, '{}', '')\n"
            "    def __exit__(self, *args: object) -> None:\n"
            "        self.calls.append('exit')\n"
        ).encode()

    def driver(self, name: str) -> checker.Driver:
        """Initialize a real driver, replacing only its unrelated home-init CLI."""

        def initialize(driver: checker.Driver, *args: str) -> None:
            """Supply the standalone config normally written by home init."""
            self.assertEqual(args, ("home", "init", "--mode", "standalone"))
            driver.home.mkdir()
            (driver.home / "config.yaml").write_text(
                "runtime: {mode: standalone}\npolicy: {}\n"
            )

        with (
            patch.object(checker.Driver, "cli", initialize),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return checker.Driver(
                Path("/unused/transist"), self.checkout, self.root, name
            )

    def test_unchanged_source_reuses_exact_class_without_reexecution(self) -> None:
        """Real repeated loads share class identity and the original byte digest."""
        loaded = checker.peer_controller(self.checkout)
        self.assertEqual(self.executed.read_text(), "A")
        self.executed.write_text("not reexecuted")
        again = checker.peer_controller(self.checkout)
        self.assertIs(again, loaded)
        self.assertIs(again.controller, loaded.controller)
        self.assertEqual(loaded.path, self.path)
        self.assertEqual(loaded.sha256, hashlib.sha256(self.source_a).hexdigest())
        self.assertEqual(loaded.source, self.source_a)
        module = sys.modules[loaded.controller.__module__]
        self.assertIs(module.SOURCE_BYTES, loaded.source)
        self.assertEqual(module.HELPER_SHA256, loaded.sha256)
        self.assertEqual(loaded.controller.implementation, "A")
        self.assertEqual(self.executed.read_text(), "not reexecuted")

    def test_same_path_same_size_replacement_rejects_cached_class(self) -> None:
        """Equal-size content replacement cannot relabel a path-cached controller."""
        loaded = checker.peer_controller(self.checkout)
        self.assertEqual(len(self.source_a), len(self.source_b))
        replacement = self.path.with_suffix(".replacement")
        replacement.write_bytes(self.source_b)
        replacement.replace(self.path)
        with self.assertRaisesRegex(checker.CheckError, "peer helper source changed"):
            checker.peer_controller(self.checkout)
        self.assertEqual(self.executed.read_text(), "A")
        self.assertEqual(loaded.controller.calls, [])
        self.path.write_bytes(self.source_a)
        self.assertIs(checker.peer_controller(self.checkout), loaded)

    def test_read_exec_race_compiles_captured_bytes_and_rejects_drift(self) -> None:
        """A deterministic read/exec race executes A, never rereads B as code."""
        read_bytes = Path.read_bytes
        reads = []

        def replace_after_capture(path: Path) -> bytes:
            """Replace the selected file after returning its actual original bytes."""
            content = read_bytes(path)
            if path == self.path:
                reads.append(content)
                self.path.write_bytes(self.source_b)
            return content

        with patch.object(Path, "read_bytes", replace_after_capture):
            with self.assertRaisesRegex(
                checker.CheckError, "peer helper source changed"
            ):
                checker.peer_controller(self.checkout)
        self.assertEqual(reads, [self.source_a, self.source_b])
        self.assertEqual(self.executed.read_text(), "A")
        self.assertNotIn(self.path, checker._PEER_HELPERS)
        self.assertFalse(
            any(
                getattr(module, "__file__", None) == str(self.path)
                for module in sys.modules.copy().values()
            )
        )
        loaded = checker.peer_controller(self.checkout)
        self.assertEqual(loaded.controller.implementation, "B")
        self.assertEqual(loaded.sha256, hashlib.sha256(self.source_b).hexdigest())

    def test_init_to_first_scope_drift_fails_before_dispatch(self) -> None:
        """Driver initialization pins A; replacing it before scope cannot invoke B."""
        driver = self.driver("pinned")
        self.path.write_bytes(self.source_b)
        with self.assertRaisesRegex(checker.CheckError, "peer helper source changed"):
            with driver.peers([]):
                self.fail("changed helper entered a peer scope")
        self.assertEqual(driver.peer_helper.controller.calls, [])
        self.assertEqual(driver.transport_sequence, 0)
        self.assertIsNone(driver.transport)
        self.assertFalse((driver.root / "peer-helper.json").exists())
        self.assertEqual(self.executed.read_text(), "A")

    def test_multi_driver_scope_receipts_stay_loaded_and_reject_drift(self) -> None:
        """Scope receipts identify loaded A, including after a mid-scope edit."""
        drivers = [self.driver("one"), self.driver("two")]
        loaded = drivers[0].peer_helper
        self.assertIs(drivers[1].peer_helper, loaded)
        expected = {"path": str(self.path), "sha256": loaded.sha256}
        self.assertEqual(expected["sha256"], hashlib.sha256(self.source_a).hexdigest())
        for driver in drivers:
            for _ in range(2):
                with driver.peers([]):
                    driver.cli("workflows", "explain", "fixture")
                for name in (
                    "peer-helper.json",
                    f"peer-helper-{driver.transport_sequence}.json",
                ):
                    self.assertEqual(
                        json.loads((driver.root / name).read_text()), expected
                    )
        with drivers[0].peers([]):
            self.path.write_bytes(self.source_b)
            drivers[0].cli("workflows", "explain", "still-loaded-A")
            self.assertEqual(
                json.loads((drivers[0].root / "peer-helper-3.json").read_text()),
                expected,
            )
        self.assertEqual(loaded.controller.calls, ["enter", "run", "exit"] * 5)
        for driver in drivers:
            before = driver.transport_sequence
            with self.assertRaisesRegex(
                checker.CheckError, "peer helper source changed"
            ):
                with driver.peers([]):
                    self.fail("changed helper entered a later scope")
            self.assertEqual(driver.transport_sequence, before)
            self.assertEqual(
                json.loads((driver.root / "peer-helper.json").read_text()),
                expected,
            )
        with self.assertRaisesRegex(checker.CheckError, "peer helper source changed"):
            self.driver("new-after-drift")
        self.assertEqual(loaded.controller.calls, ["enter", "run", "exit"] * 5)

    def test_selected_checkouts_keep_classes_distinct_for_identical_bytes(self) -> None:
        """Only the selected checkout supplies code; another root has its own class."""
        loaded = checker.peer_controller(self.checkout)
        other = self.root / "other"
        (other / "tests").mkdir(parents=True)
        other_path = other / "tests/namespace_peers.py"
        other_path.write_bytes(self.source_a)
        selected = checker.peer_controller(other)
        self.assertIsNot(selected.controller, loaded.controller)
        self.assertEqual(selected.sha256, loaded.sha256)
        self.assertEqual(selected.path, other_path)
        self.path.write_bytes(self.source_b)
        with self.assertRaisesRegex(checker.CheckError, "peer helper source changed"):
            checker.peer_controller(self.checkout)
        self.assertIs(checker.peer_controller(other), selected)

    def test_selected_checkout_and_helper_symlinks_fail_closed(self) -> None:
        """An explicit root cannot import a sibling or follow a helper symlink."""
        outside = self.root / "outside.py"
        outside.write_bytes(self.source_b)
        self.path.unlink()
        self.path.symlink_to(outside)
        with self.assertRaises(checker.CheckError):
            checker.peer_controller(self.checkout)
        self.path.unlink()
        (self.checkout / "tests").rmdir()
        (self.checkout / "tests").symlink_to(self.root)
        (self.root / "namespace_peers.py").write_bytes(self.source_b)
        with self.assertRaises(checker.CheckError):
            checker.peer_controller(self.checkout)
        alias = self.root / "alias"
        alias.symlink_to(self.checkout, target_is_directory=True)
        with self.assertRaises(checker.CheckError):
            checker.peer_controller(alias)
        with self.assertRaises(checker.CheckError):
            checker.peer_controller(Path("selected"))
        self.assertFalse(self.executed.exists())

    def test_missing_or_incorrect_source_binding_api_fails_closed(self) -> None:
        """Older pathname helpers and dishonest binding claims cannot be cached."""
        for binding in (
            "",
            "SOURCE_BYTES = b'other bytes'\n"
            "HELPER_SHA256 = globals()['__namespace_peers_expected_sha256__']\n",
            "SOURCE_BYTES = globals()['__namespace_peers_source__']\n"
            "HELPER_SHA256 = 'incorrect'\n",
        ):
            with self.subTest(binding=binding):
                self.path.write_text(
                    binding + "class NamespacePeers:\n"
                    "    def __init__(self):\n"
                    "        raise AssertionError('controller must not start')\n"
                )
                with self.assertRaisesRegex(
                    checker.CheckError, "captured-source binding API"
                ):
                    checker.peer_controller(self.checkout)
                self.assertNotIn(self.path, checker._PEER_HELPERS)


if __name__ == "__main__":
    unittest.main()
