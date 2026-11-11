"""Workflow-owned feedback/PR formatting and actual typed-control regressions.

Provider algorithms and their golden cases moved with Step 7 to git.cli and
github.cli. Installed delivery fixtures exercise those real actions; these units
cover the remaining workflow boundary rather than retaining obsolete executables.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

EXAMPLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "feedback", EXAMPLE / "modules/scripts/write_operator_feedback.py"
)
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)


def evaluate(expression: str, outputs: dict) -> bool:
    """Bind synthetic typed outputs to the actual authored comparison expression."""
    text = re.sub(
        r"steps\.[A-Za-z0-9_.]+", lambda match: repr(outputs.get(match[0])), expression
    )
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"(?<![\w\"'])true(?![\w\"'])", "True", text)
    tree = ast.parse(text, mode="eval")
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Constant,
        ast.Load,
    )
    assert all(isinstance(node, allowed) for node in ast.walk(tree))
    return bool(eval(compile(tree, "<authored control>", "eval"), {"__builtins__": {}}))


class GateFeedbackTests(unittest.TestCase):
    """Only exact runtime-bound current request-change reasons become feedback."""

    def decision(self, **changes: object) -> dict:
        """Return a complete synthetic immutable gate decision."""
        return {
            "schema": "transist.gate_decision.v1",
            "run_id": "example-run",
            "gate_id": "review-cycle-decision",
            "step_id": "review_cycle_decision",
            "decision": "request_changes",
            "reason": "  Add regression coverage  ",
            "decided_at_ms": 1,
            **changes,
        }

    def test_only_valid_request_changes_delivers_reason(self) -> None:
        """Retain approval/rejection, malformed/type, absence and freshness cases."""
        cases = [(self.decision(), "Add regression coverage")]
        cases += [
            (self.decision(**{key: value}), "")
            for key, value in (
                ("decision", "approved"),
                ("decision", "rejected"),
                ("decision", "approve"),
                ("schema", "wrong"),
                ("run_id", ""),
                ("gate_id", None),
                ("step_id", " "),
                ("decided_at_ms", True),
                ("decided_at_ms", -1),
                ("reason", []),
                ("extra", "field"),
            )
        ]
        cases += [({}, ""), ([], "")]
        for record, expected in cases:
            with self.subTest(record=record), patch.dict(
                os.environ,
                {"TRANSIST_GATE_DECISION_JSON": json.dumps(record)},
                clear=True,
            ):
                self.assertEqual(feedback._operator_reason_from_environment(), expected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(feedback._operator_reason_from_environment(), "")
        with patch.dict(
            os.environ, {"TRANSIST_GATE_DECISION_JSON": "{"}, clear=True
        ), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(feedback._operator_reason_from_environment(), "")

    def test_feedback_overwrites_old_cycle_and_excludes_bot_replies(self) -> None:
        """Preserve ordering/location and replace stale reasons each cycle."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            comments, output = root / "comments.json", root / "feedback.md"
            comments.write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "source": "review_thread",
                                "path": "src/example.py",
                                "body": "Fix edge case",
                            },
                            {"source": "pr_conversation", "body": "Add coverage"},
                            {
                                "body": "  <!-- transist-review-reply --> "
                                "Already handled"
                            },
                            "invalid",
                        ]
                    }
                )
            )
            args = [
                "feedback",
                "--review-comments-file",
                str(comments),
                "--output-file",
                str(output),
            ]
            with patch.object(sys, "argv", args), patch.dict(
                os.environ,
                {"TRANSIST_GATE_DECISION_JSON": json.dumps(self.decision())},
                clear=True,
            ), contextlib.redirect_stderr(io.StringIO()):
                feedback.main()
            content = output.read_text()
            self.assertLess(
                content.index("Operator Instructions"),
                content.index("Unresolved PR Comments"),
            )
            self.assertIn("src/example.py", content)
            self.assertIn("Add coverage", content)
            self.assertNotIn("Already handled", content)
            comments.write_text('{"comments":[]}')
            with patch.object(sys, "argv", args), patch.dict(
                os.environ, {}, clear=True
            ), contextlib.redirect_stderr(io.StringIO()):
                feedback.main()
            self.assertEqual(output.read_bytes(), b"")

    def test_review_metadata_keeps_feedback_and_invalid_new_record_is_explicit(
        self,
    ) -> None:
        """Keep valid review feedback and explicitly reject invalid new records."""
        record = self.decision(
            review_request={
                "schema": "transist.gate_review_request.v1",
                "run_id": "example-run",
                "gate_id": "review-cycle-decision",
                "step_id": "review_cycle_decision",
                "execution": 1,
                "review_documents": [
                    {
                        "schema": "transist.document_revision.v1",
                        "root_run_id": "example-run",
                        "run_id": "example-run",
                        "step_id": "author",
                        "execution": 1,
                        "commit_sequence": 1,
                        "revision_id": "b" * 64,
                        "document": "notes",
                        "kind": "file",
                        "size_bytes": 1,
                        "file_count": 1,
                        "blob": {"sha256": "a" * 64, "size_bytes": 1},
                    }
                ],
            }
        )
        with patch.dict(
            os.environ, {"TRANSIST_GATE_DECISION_JSON": json.dumps(record)}, clear=True
        ):
            self.assertEqual(
                feedback._operator_reason_from_environment(), "Add regression coverage"
            )
        with patch.dict(
            os.environ,
            {
                "TRANSIST_GATE_DECISION_JSON": json.dumps(
                    {**record, "decided_at_ms": 1.0}
                )
            },
            clear=True,
        ):
            with self.assertRaises(ValueError):
                feedback._operator_reason_from_environment()


class TypedPRExitTests(unittest.TestCase):
    """Actual guards use typed actions and cannot exit while a child is blocked."""

    def test_actual_auto_exit_truth_table(self) -> None:
        """Preserve open/check requirements, merged exit and explicit override."""
        doc = yaml.safe_load((EXAMPLE / "modules/pr_review.module.yaml").read_text())
        expression = doc["steps"][0]["loop"]["until"]
        prefix = "steps.review_cycle.out."
        for state, approval, merge, decision, status, expected in (
            ("OPEN", True, True, None, "success", True),
            ("OPEN", False, True, None, "success", False),
            ("OPEN", True, False, None, "success", False),
            ("CLOSED", True, True, None, "success", False),
            (None, None, None, None, "success", False),
            ("MERGED", False, False, None, "success", True),
            ("OPEN", False, False, "approved", "success", True),
            ("OPEN", None, None, "approved", "blocked", False),
        ):
            self.assertIs(
                evaluate(
                    expression,
                    {
                        prefix + "state": state,
                        prefix + "approval_ready": approval,
                        prefix + "merge_ready": merge,
                        prefix + "status": status,
                        prefix
                        + "child_steps.review_cycle_decision.out.decision": decision,
                    },
                ),
                expected,
            )

    def test_soft_fail_and_direct_boolean_contracts(self) -> None:
        """Negative readiness branches directly, without shell Boolean extraction."""
        doc = yaml.safe_load(
            (EXAMPLE / "modules/pr_review_cycle.module.yaml").read_text()
        )
        steps = {step["id"]: step for step in doc["steps"]}
        self.assertEqual(
            steps["check_pr_exit_approvals"]["uses"],
            "process:github.cli/pr_check_approvals",
        )
        self.assertIs(steps["check_pr_exit_approvals"]["with"]["soft_fail"], True)
        self.assertEqual(
            steps["check_pr_exit_mergeability"]["uses"],
            "process:github.cli/pr_check_mergeability",
        )
        self.assertNotIn("read_json_bool", str(doc))
        self.assertNotIn("vars.", str(doc))


class ComposeTests(unittest.TestCase):
    """Run the real staged-data formatter, including same-file use."""

    def test_footer_removal_replacement_same_file_and_missing_sources(self) -> None:
        """Retain footer, optional metadata, idempotence and temp cleanup cases."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            body, output, metadata = (
                root / name
                for name in ("body with spaces.md", "output.md", "metadata.json")
            )
            body.write_text(
                "## What Changed\nExample fix\n<!-- transist-pr-callout:start -->\n"
                "Old runtime\n<!-- transist-pr-callout:end -->\n"
            )
            metadata.write_text(
                json.dumps(
                    {
                        "runtime": {"version": "0.1.1"},
                        "workflow": {
                            "id": "hotfix_ticket_delivery",
                            "version": "0.1.0",
                        },
                        "plugins": [{"name": "shell", "version": "0.1.0"}],
                    }
                )
            )
            env = {"PATH": os.environ["PATH"], "TMPDIR": str(root)}
            command = [
                "bash",
                str(EXAMPLE / "scripts/compose_pr_body_for_open.sh"),
                "--source-body-file",
                str(body),
                "--output-body-file",
                str(output),
            ]
            subprocess.run(command, env=env, check=True, capture_output=True)
            self.assertEqual(output.read_text(), "## What Changed\nExample fix\n")
            enabled = [
                *command,
                "--include-transist-pr-callout",
                "YES",
                "--runtime-metadata-file",
                str(metadata),
            ]
            subprocess.run(enabled, env=env, check=True, capture_output=True)
            content = output.read_text()
            self.assertNotIn("Old runtime", content)
            self.assertIn("hotfix_ticket_delivery@0.1.0", content)
            self.assertIn("shell@0.1.0", content)
            same = enabled.copy()
            same[same.index("--source-body-file") + 1] = str(output)
            subprocess.run(same, env=env, check=True, capture_output=True)
            self.assertEqual(output.read_text().count("transist-pr-callout:start"), 1)
            metadata.unlink()
            subprocess.run(enabled, env=env, check=True, capture_output=True)
            self.assertEqual(output.read_text(), "## What Changed\nExample fix\n")
            body.unlink()
            self.assertNotEqual(
                subprocess.run(command, env=env, capture_output=True).returncode, 0
            )
            self.assertFalse(list(root.glob("compose-pr-*")))


if __name__ == "__main__":
    unittest.main()
