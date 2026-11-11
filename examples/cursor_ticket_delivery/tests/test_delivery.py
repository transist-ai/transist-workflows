"""Typed authored controls and contained data helpers; no obsolete CLI oracles.

GitHub normalization/reviewer/transport behavior moved with the Step 7 actions.
These cases retain the workflow truth tables using actual authored expressions.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

EXAMPLE = Path(__file__).resolve().parents[1]
HELPERS = EXAMPLE / "modules/scripts"


def load_helper(name: str) -> object:
    """Import one current contained data helper without invoking its command."""
    spec = importlib.util.spec_from_file_location(name, HELPERS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def document(name: str) -> dict:
    """Read the actual current module, not a duplicate test recipe."""
    return yaml.safe_load((EXAMPLE / "modules" / f"{name}.module.yaml").read_text())


def evaluate_guard(expression: str, outputs: dict) -> bool:
    """Evaluate the authored comparison/Boolean subset with JSON Boolean identity."""
    text = re.sub(
        r"steps\.[A-Za-z0-9_.]+", lambda match: repr(outputs.get(match[0])), expression
    )
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"(?<![\w\"'])true(?![\w\"'])", "True", text)
    text = re.sub(r"(?<![\w\"'])false(?![\w\"'])", "False", text)

    def value(node: ast.AST) -> object:
        """Handle only the explicit grammar used in these immutable definitions."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = (bool(value(child)) for child in node.values)
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = value(node.left), value(node.comparators[0])
            equal = (
                (type(left) is type(right) and left == right)
                if isinstance(left, bool) or isinstance(right, bool)
                else left == right
            )
            if isinstance(node.ops[0], ast.Eq):
                return equal
            if isinstance(node.ops[0], ast.NotEq):
                return not equal
        raise AssertionError("unsupported authored guard grammar")

    return bool(value(ast.parse(text, mode="eval").body))


class ExitCleanTests(unittest.TestCase):
    """Only current structured producer outputs select automatic exit."""

    def evaluate(self, pr: dict, validation: object = True, **checks: object) -> dict:
        """Bind producer fields to the actual inner automatic-exit control."""
        state = pr.get("pull_request", pr)
        state = state.get("state") if isinstance(state, dict) else None
        steps = {step["id"]: step for step in document("pr_review_cycle")["steps"]}
        pause = evaluate_guard(
            steps["should_pause_for_review"]["if"]["guard"],
            {
                "steps.inspect_pr_state.out.pull_request.state": state,
                "steps.check_pr_exit_approvals.out.approval_ready": checks.get(
                    "approval", True
                ),
                "steps.check_pr_exit_mergeability.out.merge_ready": checks.get(
                    "merge", True
                ),
                "steps.check_pr_exit_validation.out.passed": validation,
            },
        )
        return {"exit_clean": not pause, "state": state}

    def test_public_wrapped_open_pr_passes(self) -> None:
        """The public wrapped OPEN state supports automatic clean exit."""
        self.assertTrue(
            self.evaluate({"pull_request": {"state": "OPEN"}})["exit_clean"]
        )

    def test_raw_github_open_fixture_passes(self) -> None:
        """The conforming GitHub OPEN value maps to the same producer state."""
        self.assertTrue(self.evaluate({"state": "OPEN"})["exit_clean"])

    def test_wrapped_state_overrides_conflicting_top_level_state(self) -> None:
        """A malformed, missing, closed or merged wrapped state cannot fall back."""
        for wrapped in ({"state": "CLOSED"}, {"state": "MERGED"}, {}, None, []):
            self.assertFalse(
                self.evaluate({"state": "OPEN", "pull_request": wrapped})["exit_clean"]
            )

    def test_closed_missing_or_malformed_pr_cannot_pass(self) -> None:
        """Unusable current state pauses before any automatic exit."""
        for state in ("CLOSED", "MERGED", "", None, "unknown"):
            self.assertFalse(self.evaluate({"state": state})["exit_clean"])

    def test_failed_missing_or_nonboolean_verification_cannot_pass(self) -> None:
        """Only actual Boolean verification permits automatic exit."""
        for verdict in (False, None, "true", "false", 1, 0):
            self.assertFalse(self.evaluate({"state": "OPEN"}, verdict)["exit_clean"])

    def test_readiness_requires_json_booleans(self) -> None:
        """False-like strings/numbers cannot substitute for typed action results."""
        for field in ("approval", "merge"):
            for result in (False, None, "true", "false", 1, 0):
                self.assertFalse(
                    self.evaluate({"state": "OPEN"}, **{field: result})["exit_clean"]
                )

    def test_stale_or_malformed_report_files_cannot_supply_a_verdict(self) -> None:
        """A previous positive report cannot replace the current structured output."""
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "validation_report.md"
            for text in ("## Verdict\nPASS", "[]", "null", "{", "Materially aligned"):
                report.write_text(text)
                self.assertFalse(self.evaluate({"state": "OPEN"}, None)["exit_clean"])
            self.assertTrue(self.evaluate({"state": "OPEN"}, True)["exit_clean"])


class ReviewedPlanCopyTests(unittest.TestCase):
    """Only the explicit OpenSpec deliverable is copied into the workspace."""

    def test_staged_bytes_required_exact_without_private_permissions(self) -> None:
        """Missing staged source never falls back to a stale workspace plan."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repo, staged = root / "workspace", root / "managed-read"
            repo.mkdir()
            staged.write_bytes(b"  # Approved plan\r\nExact bytes.\n")
            staged.chmod(0o400)
            args = [
                sys.executable,
                "-B",
                str(HELPERS / "relocate_plan_md.py"),
                "--plan-file",
                str(staged),
                "--repo-path",
                str(repo),
                "--change-name",
                "PROJ-123",
            ]
            subprocess.run(args, check=True, capture_output=True, timeout=15)
            target = repo / "openspec/changes/proj-123/plan.md"
            self.assertEqual(target.read_bytes(), staged.read_bytes())
            self.assertTrue(target.stat().st_mode & 0o200)
            self.assertFalse((repo / ".transist").exists())
            staged.unlink()
            self.assertNotEqual(
                subprocess.run(args, capture_output=True, timeout=15).returncode, 0
            )
            self.assertEqual(
                target.read_bytes(), b"  # Approved plan\r\nExact bytes.\n"
            )


class ReviewGuardTests(unittest.TestCase):
    """Preserve both manual overrides while guarding named exports until completion."""

    def loop_exits(
        self,
        primary: str | None,
        extra: str | None,
        passed: bool = False,
        approvals: bool = True,
        merge: bool = True,
        clean: bool = False,
        state: str = "OPEN",
        child_status: str = "success",
    ) -> bool:
        """Bind one current child cycle to the actual outer-loop expression."""
        prefix = "steps.review_cycle.out."
        return evaluate_guard(
            document("pr_review")["steps"][0]["loop"]["until"],
            {
                prefix + "state": state,
                prefix + "status": child_status,
                prefix + "approval_ready": approvals,
                prefix + "merge_ready": merge,
                prefix + "child_steps.review_cycle_decision.out.decision": primary,
                prefix
                + "child_steps.review_exit_after_failed_validation.out.decision": extra,
                prefix + "child_steps.check_pr_exit_validation.out.passed": passed
                or clean,
            },
        )

    def test_extra_request_changes_vetoes_primary_approval(self) -> None:
        """The validation override cannot be skipped after initial approval."""
        self.assertFalse(self.loop_exits("approved", "request_changes"))
        for extra in (None, "rejected"):
            self.assertFalse(self.loop_exits("approved", extra))
        self.assertTrue(self.loop_exits("approved", "approved"))

    def test_blocked_child_cannot_exit_with_absent_named_exports(self) -> None:
        """Pending decisions must be processed before the parent completes."""
        for status in ("blocked", "failed", None):
            self.assertFalse(
                self.loop_exits(
                    "approved", None, approvals=None, merge=None, child_status=status
                )
            )

    def test_normal_and_explicit_override_exits(self) -> None:
        """Preserve automatic, already-merged and intentionally overridden exits."""
        self.assertTrue(self.loop_exits(None, None, passed=True))
        self.assertTrue(self.loop_exits(None, None, state="MERGED"))
        self.assertTrue(self.loop_exits("approved", None, approvals=False))
        self.assertTrue(self.loop_exits("approved", None, merge=False))
        for primary in (None, "rejected", "request_changes"):
            self.assertFalse(self.loop_exits(primary, None))

    def test_current_verdict_and_empty_feedback_branches(self) -> None:
        """Current Boolean output selects resolution; empty feedback still refreshes."""
        steps = {step["id"]: step for step in document("pr_review_cycle")["steps"]}
        inputs = {
            "steps.check_pr_exit_approvals.out.approval_ready": True,
            "steps.check_pr_exit_mergeability.out.merge_ready": True,
            "steps.inspect_pr_state.out.pull_request.state": "OPEN",
        }
        guard = steps["maybe_render_validation_resolved_comment"]["if"]["guard"]
        for verdict in (True, False, None, "true", 1):
            self.assertIs(
                evaluate_guard(
                    guard,
                    {**inputs, "steps.check_pr_exit_validation.out.passed": verdict},
                ),
                verdict is True,
            )
        refresh = steps["maybe_refresh_review_state_after_failed_validation"]["if"][
            "guard"
        ]
        self.assertTrue(
            evaluate_guard(
                refresh,
                {
                    "steps.review_exit_after_failed_validation.out.decision": (
                        "request_changes"
                    )
                },
            )
        )

    def test_remediation_model_inherits_root_input(self) -> None:
        """Root verification models reach the action without forwarding."""
        child = document("validation_remediation_iteration")
        self.assertEqual(
            child["profiles"]["verify"]["with"]["model"], "{{inputs.openspec_model}}"
        )
        self.assertNotIn("inputs", child)


if __name__ == "__main__":
    unittest.main()
