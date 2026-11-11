"""Offline regressions for advisory validation, execution selection and review."""

import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "edge_fault_advisory"
SPEC = importlib.util.spec_from_file_location("edge_runner", EXAMPLE / "run_local.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class EdgeRunnerTests(unittest.TestCase):
    """Test fail-closed decisions without starting any runtime or provider."""

    def test_ready_report(self) -> None:
        """Accept only complete passing readiness evidence."""
        report = {
            "schema": "transist.workflow_readiness.v1",
            "status": "ready",
            "run_created": False,
            "checks": [{"status": "passed"}],
        }
        self.assertEqual(runner.readiness_report(json.dumps(report)), report)
        for field, value in (
            ("schema", "wrong"),
            ("status", "not_ready"),
            ("run_created", True),
            ("checks", []),
            ("checks", [{"status": "failed"}]),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(RuntimeError):
                    runner.readiness_report(json.dumps({**report, field: value}))
        for malformed in ("garbage", "[]", "null"):
            with self.assertRaises(RuntimeError):
                runner.readiness_report(malformed)
        deferred = {
            **report,
            "checks": [
                {"status": "deferred_to_dispatch", "code": "input_schema"},
                {"status": "deferred_to_dispatch", "code": "deferred_to_dispatch"},
            ],
        }
        runner.readiness_report(json.dumps(deferred))
        for code in ("step_policy", "secret_resolution", "plugin_contract"):
            with self.assertRaises(RuntimeError):
                runner.readiness_report(
                    json.dumps(
                        {
                            **report,
                            "checks": [
                                {"status": "deferred_to_dispatch", "code": code}
                            ],
                        }
                    )
                )

    def gate_state(self) -> dict:
        """Return the current runtime's blocked document review shape."""
        return {
            "status": "blocked",
            "steps": {
                "diagnostic_transfer": {
                    "status": "blocked",
                    "last_result": {
                        "output": {
                            "review_request": {
                                "step_id": "diagnostic_transfer",
                                "gate_id": "diagnostic-transfer",
                                "review_documents": [
                                    {
                                        "document": "diagnostic",
                                        "revision_id": "revision",
                                        "blob": {"sha256": "digest"},
                                    }
                                ],
                            }
                        }
                    },
                }
            },
        }

    def test_gate_and_document(self) -> None:
        """Only an actual blocked document gate is accepted; no workspace equality."""
        state = self.gate_state()
        runner.verify_gate(state)
        for status in ("waiting", "failed", "success"):
            with self.assertRaises(RuntimeError):
                runner.verify_gate({**state, "status": status})
        state["steps"]["diagnostic_transfer"]["last_result"]["output"][
            "review_request"
        ]["review_documents"] = []
        with self.assertRaises(RuntimeError):
            runner.verify_gate(state)

    def test_sample_selects_workspace_file(self) -> None:
        """The sample supplies a path, never a duplicate diagnostic payload."""
        sample = yaml.safe_load((EXAMPLE / "inputs.example.yaml").read_text())
        self.assertNotIn("diagnostic_text", sample)
        self.assertEqual(sample["diagnostic_path"], "diagnostics.txt")

    def test_gate_binds_exact_document_revision(self) -> None:
        """Capture, gate and provider connect through managed document bindings."""
        workflow = yaml.safe_load((EXAMPLE / "workflow.yaml").read_text())
        self.assertEqual(workflow["version"], "0.1.0")
        self.assertEqual(runner.WORKFLOW, "edge_fault_advisory@0.1.0")
        steps = {step["id"]: step for step in workflow["steps"]}
        gate = steps["diagnostic_transfer"]
        self.assertEqual(gate["control"], "control.gate.manual")
        review = gate["with"]
        self.assertEqual(review["gate_id"], "diagnostic-transfer")
        self.assertEqual(review["review_documents"], ["diagnostic"])
        self.assertEqual(steps["read_diagnostics"]["uses"], "process:shell/read_file")
        self.assertEqual(
            steps["read_diagnostics"]["with"]["output_file"],
            {"$document": "diagnostic", "access": "write"},
        )
        provider = steps["advise"]["with"]
        self.assertEqual(review["destination"], provider["base_url"])
        self.assertEqual(review["model"], provider["model"])
        self.assertNotIn("messages", provider)
        self.assertNotIn("prompt_file", steps["advise"])
        self.assertIn("technician adviser", provider["system_prompt"])
        self.assertEqual(
            provider["user_text_file"],
            {
                "$document": "diagnostic",
                "access": "read",
                "reviewed_by": "diagnostic_transfer",
            },
        )
        self.assertEqual(
            provider["response_file"], {"$document": "response", "access": "write"}
        )
        self.assertEqual(provider["secret_refs"], ["OPENAI_COMPATIBLE_API_KEY"])

    def test_launcher_requires_separate_execution_selection(self) -> None:
        """Validation never starts a run; execution stops at review, no approval."""
        for execute in (False, True):
            with self.subTest(
                execute=execute
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace = root / "workspace"
                # No diagnostic exists: the launcher must not pre-read.
                workspace.mkdir()
                home = root / "home"
                calls = []

                def cli(_binary: Path, _home: Path, _env: dict, *args: str) -> str:
                    """Create only synthetic config and return current CLI evidence."""
                    calls.append(args)
                    if args[:2] == ("home", "init"):
                        home.mkdir()
                        (home / "config.yaml").write_text(
                            "policy: {remote_secret_delivery: {process: false}}"
                        )
                    if args[:2] == ("workflows", "check"):
                        return json.dumps(
                            {
                                "schema": "transist.workflow_readiness.v1",
                                "status": "ready",
                                "run_created": False,
                                "checks": [{"status": "passed"}],
                            }
                        )
                    return json.dumps(self.gate_state())

                arguments = [
                    "--transist",
                    "/bin/sh",
                    "--model",
                    "fixture",
                    "--shell-manifest",
                    "shell",
                    "--openai-manifest",
                    "openai",
                    "--workspace",
                    str(workspace),
                ] + (["--execute"] if execute else [])
                with patch.object(
                    runner, "manifest", return_value=Path("/fixture/plugin.yaml")
                ), patch.object(
                    runner.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, "transist 0.1.1\n"),
                ), patch.object(
                    runner.tempfile, "mkdtemp", return_value=str(root)
                ), patch.object(
                    runner, "execute", side_effect=cli
                ), patch.dict(
                    "os.environ", {"OPENAI_COMPATIBLE_API_KEY": "dummy-fixture"}
                ), contextlib.redirect_stdout(
                    io.StringIO()
                ):
                    self.assertEqual(runner.main(arguments), 0)
                self.assertEqual(
                    any(call[:2] == ("workflows", "run") for call in calls), execute
                )
                self.assertFalse(any(call[:2] == ("runs", "gate") for call in calls))

    def test_manifest_parser(self) -> None:
        """Parse exact pins; other releases are exempt negative-policy fixtures."""
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            manifest = Path(directory) / "plugin.yaml"
            manifest.write_text(
                "schema: transist.plugin.v1\nid: 'shell'\nversion: '0.1.0'\n"
            )
            self.assertEqual(
                runner.manifest(str(manifest), "shell", "0.1.0"), manifest.resolve()
            )
            with self.assertRaises(ValueError):
                runner.manifest(str(manifest), "another-plugin", "0.1.0")
            for version in ("1.0.0", "v1", "0.1.1", "0.1.0-beta.1"):
                with self.subTest(version=version):
                    manifest.write_text(
                        f"schema: transist.plugin.v1\nid: shell\nversion: {version}\n"
                    )
                    with self.assertRaisesRegex(ValueError, "Expected shell@0.1.0"):
                        runner.manifest(str(manifest), "shell", "0.1.0")

    def test_nonzero_and_timeout_do_not_expose_output(self) -> None:
        """CLI failures propagate before run creation, without raw output."""
        result = subprocess.CompletedProcess(
            [], 1, "sensitive-fixture", "sensitive-fixture"
        )
        with patch.object(runner.subprocess, "run", return_value=result):
            with self.assertRaises(RuntimeError) as caught:
                runner.execute(
                    Path("/example/transist"),
                    Path("/tmp/example"),
                    {},
                    "workflows",
                    "check",
                )
            self.assertNotIn("sensitive-fixture", str(caught.exception))
        with patch.object(
            runner.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("fixture", 1),
        ):
            with self.assertRaises(RuntimeError):
                runner.execute(
                    Path("/example/transist"),
                    Path("/tmp/example"),
                    {},
                    "workflows",
                    "check",
                )


if __name__ == "__main__":
    unittest.main()
