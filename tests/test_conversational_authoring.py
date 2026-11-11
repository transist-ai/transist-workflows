"""Finite authoring inventory, intended revision and fail-closed runner regressions."""

import contextlib
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_authoring_fixtures as authoring  # noqa: E402
from check_examples import CheckError, inspect_graph, load_yaml  # noqa: E402


class AuthoringFixtureTests(unittest.TestCase):
    """Definitions remain real catalog graphs, not a parallel execution DSL."""

    def test_finite_inventory_and_real_action_shapes(self) -> None:
        """All three roots/pins/assets are required without extending EXAMPLES."""
        self.assertEqual(authoring.select([]), list(authoring.INVENTORY))
        self.assertEqual(
            authoring.select(["diagnostic_advisory"] * 2), ["diagnostic_advisory"]
        )
        with self.assertRaises(CheckError):
            authoring.select(["missing"])
        for name in authoring.INVENTORY:
            path = authoring.FIXTURES / name / "workflow.yaml"
            flow, pins, actions = inspect_graph(path)
            self.assertEqual(set(pins.values()), {"0.1.0"})
            self.assertEqual(flow["workspace"]["access"], "read_only")
            self.assertIn("process:openai.compatible/chat_complete", actions)
            self.assertIn("process:shell/read_file", actions)
            self.assertNotIn("process:shell/exec", actions)
            self.assertTrue((path.parent / "inputs.example.yaml").is_file())
            self.assertTrue((path.parent / "walkthrough.md").is_file())

    def test_exact_intended_revision(self) -> None:
        """Only a second distinct gate/protected read changes; authority/pins do not."""
        authoring.revision_contract()
        flow = load_yaml(authoring.FIXTURES / "two_approval_revision/workflow.yaml")
        gates = [s for s in flow["steps"] if s.get("control") == "control.gate.manual"]
        self.assertEqual(
            [g["id"] for g in gates], ["review_draft", "review_publication"]
        )
        self.assertEqual(len({g["with"]["gate_id"] for g in gates}), 2)
        self.assertEqual(
            authoring.SCENARIOS["two_approval_revision"],
            ("approved", "reject_first", "reject_second", "changed"),
        )

    def test_same_loopback_rebinding_for_both_revisions(self) -> None:
        """Fixture port binding does not introduce authority or content divergence."""
        base = load_yaml(
            authoring.FIXTURES / "approved_draft_publication/workflow.yaml"
        )
        revised = load_yaml(authoring.FIXTURES / "two_approval_revision/workflow.yaml")
        current = copy.deepcopy(revised)
        for port in (18001, 18002):
            first = authoring.relocated(base, port)
            second = authoring.relocated(revised, port)
            second["steps"].pop(-2)
            second["steps"][-1]["with"]["body_file"]["reviewed_by"] = "review_draft"
            self.assertEqual(first, second)
        self.assertEqual(revised, current)

    def test_default_runner_has_total_coverage_and_propagates_failure(self) -> None:
        """Dedicated default dispatch requires every fixture, never skips failures."""
        with patch.object(authoring, "run_fixture") as run, contextlib.redirect_stdout(
            io.StringIO()
        ):
            authoring.run_all(Path("/binary"), Path("/plugins"), Path("/fixtures"))
            self.assertEqual(
                [c.args[-1] for c in run.call_args_list], list(authoring.INVENTORY)
            )
            run.side_effect = CheckError("required scenario unavailable")
            with self.assertRaises(CheckError):
                authoring.run_all(Path("/binary"), Path("/plugins"), Path("/fixtures"))

    def test_missing_binary_is_incomplete(self) -> None:
        """CLI prerequisite failures return nonzero rather than an inventory pass."""
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(
                authoring.main(
                    [
                        "--transist",
                        str(Path(directory) / "missing"),
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


if __name__ == "__main__":
    unittest.main()
