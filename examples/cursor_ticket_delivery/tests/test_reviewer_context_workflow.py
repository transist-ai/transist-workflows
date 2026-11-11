"""Actual authored lexical gate/document wiring, including every module boundary."""

from pathlib import Path
import unittest

import yaml

EXAMPLE = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    """Read the current authored document, not a second fixture definition."""
    return yaml.safe_load((EXAMPLE / path).read_text())


class ReviewerContextWiringTests(unittest.TestCase):
    """Root identity is initialized once; all children use the same managed ledger."""

    def test_root_initialization_precedes_effects(self) -> None:
        """Input/caller path identity cannot select a ledger or begin network work."""
        root = load("workflow.yaml")
        self.assertNotIn("reviewer_context_id", root["inputs"])
        self.assertNotIn("artifact_path_prefix", root["inputs"])
        init = root["steps"][0]
        self.assertEqual(init["id"], "initialize_reviewer_context")
        self.assertEqual(
            init["with"]["args"][-1],
            {"$document": "reviewer_context", "access": "write"},
        )
        self.assertNotIn("initial", root["documents"]["reviewer_context"])

    def test_all_modules_share_documents_without_forwarding_boilerplate(self) -> None:
        """No child reinitializes identity, redefines workspace or gets ticket paths."""
        for path in (EXAMPLE / "modules").glob("*.module.yaml"):
            doc = yaml.safe_load(path.read_text())
            self.assertNotIn("workspace", doc)
            self.assertNotIn("network", doc)
            self.assertNotIn("reviewer_context_file", doc.get("inputs", {}))
            for step in doc["steps"]:
                self.assertNotEqual(step["id"], "initialize_reviewer_context")
                if "module" in step:
                    self.assertLessEqual(
                        set(step["module"].get("inputs", {})), {"stage_model"}
                    )

    def test_plan_implementation_exact_local_reviews_and_handoffs(self) -> None:
        """Gate revisions are enforced inside their own lexical recipe on export."""
        for module, gate, export in (
            ("plan_review", "review_plan", "export_reviewed_plan"),
            (
                "implementation_iteration",
                "review_implementation",
                "export_reviewed_implementation",
            ),
        ):
            doc = load(f"modules/{module}.module.yaml")
            indexed = {step["id"]: step for step in doc["steps"]}
            reviewed = set(indexed[gate]["with"]["review_documents"])
            bindings = [
                arg
                for arg in indexed[export]["with"]["args"]
                if isinstance(arg, dict) and arg.get("access") == "read"
            ]
            self.assertEqual({item["$document"] for item in bindings}, reviewed)
            self.assertTrue(all(item["reviewed_by"] == gate for item in bindings))

    def test_decision_capture_preserves_local_scope(self) -> None:
        """Every gate-bound capture updates the shared ledger in the gate's recipe."""
        for path in (EXAMPLE / "modules").glob("*.module.yaml"):
            doc = yaml.safe_load(path.read_text())
            ids = {step["id"] for step in doc["steps"]}
            for step in doc["steps"]:
                if "gate_decision" in step:
                    self.assertIn(step["gate_decision"]["step"], ids)
                    if step[
                        "uses"
                    ] == "process:shell/exec" and "reviewer_context.py" in str(
                        step["with"]["args"]
                    ):
                        self.assertIn(
                            {"$document": "reviewer_context", "access": "update"},
                            step["with"]["args"],
                        )

    def test_validation_prompts_preserve_scope_without_claiming_test_success(
        self,
    ) -> None:
        """All validator stages receive prior decisions, not automatic approval."""
        for module, validator in (
            ("workflow.yaml", "validate_changes"),
            (
                "modules/validation_remediation_iteration.module.yaml",
                "validate_changes",
            ),
            ("modules/pr_review_cycle.module.yaml", "check_pr_exit_validation"),
        ):
            step = next(
                item for item in load(module)["steps"] if item["id"] == validator
            )
            self.assertIn(
                {"$document": "reviewer_context", "access": "read"},
                step["with"]["context_files"],
            )
        prompt = (EXAMPLE / "prompts/validate_changes.md").read_text()
        for phrase in (
            "approval is not evidence of passing tests",
            "Rejected decisions are not approvals",
            "does not erase earlier requests",
        ):
            self.assertIn(phrase, prompt)


if __name__ == "__main__":
    unittest.main()
