"""Workflow-specific Git guards and actual pending-review dataflow regressions.

Scanner/projector behavior cases moved with their implementations to the Step 7
plugin suites. Installed real-action fixtures retain their integration coverage.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

EXAMPLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "working", EXAMPLE / "modules/scripts/check_working_files.py"
)
working = importlib.util.module_from_spec(spec)
spec.loader.exec_module(working)


class StorageTests(unittest.TestCase):
    """Legacy operational files cannot sneak into an all-changes commit."""

    def setUp(self) -> None:
        """Create a real isolated Git repository without required storage exclusions."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.git("init", "-q")

    def git(self, *args: str) -> None:
        """Execute only native local Git against the synthetic repository."""
        subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            check=True,
            env={
                "PATH": os.environ.get("PATH", os.defpath),
                "HOME": str(self.root),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
            },
        )

    def test_guard_never_edits_ignores_and_rejects_tracked_operational_files(
        self,
    ) -> None:
        """Forcibly tracked ignored files remain guarded; source stays valid."""
        exclude = self.root / ".git/info/exclude"
        before = exclude.read_bytes()
        working.check(self.root)
        self.assertEqual(exclude.read_bytes(), before)
        self.assertFalse((self.root / ".gitignore").exists())
        exclude.write_text("/.transist/\n*.interaction.json\n*.interaction.md\n")
        for name in (
            ".transist/context.md",
            "source.interaction.json",
            "source.interaction.md",
        ):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic operational data")
            working.check(self.root)
            self.git("add", "-f", "--", name)
            with self.assertRaisesRegex(ValueError, "operational"):
                working.check(self.root)
            self.git("rm", "--cached", "-f", "--", name)
            path.unlink()
        working.check(self.root)

    def test_stageable_untracked_interactions_fail_without_exclusion(self) -> None:
        """Managed storage needs no ignore; reject stageable legacy files."""
        for name in (
            "capture.interaction.md",
            "capture.interaction.json",
            ".transist/notes.md",
        ):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic")
            with self.assertRaisesRegex(ValueError, "operational"):
                working.check(self.root)
            path.unlink()


class PendingReviewWiringTests(unittest.TestCase):
    """Current authored post-gate actions preserve pending requests as root data."""

    def test_both_fetches_update_one_checkpoint_and_post_gate_merge_reads_pending(
        self,
    ) -> None:
        """Keep raw snapshots and pending projections in separate documents."""
        doc = yaml.safe_load(
            (EXAMPLE / "modules/pr_review_cycle.module.yaml").read_text()
        )
        steps = {step["id"]: step for step in doc["steps"]}
        for name in ("inspect_pr_comments", "refresh_pr_comments"):
            self.assertEqual(
                steps[name]["with"]["output_file"],
                {"$document": "review_comments_raw", "access": "update"},
            )
        merge = steps["merge_pending_review_comments"]
        self.assertEqual(merge["uses"], "process:github.cli/pr_prepare_review_context")
        self.assertEqual(
            merge["with"]["pending_file"],
            {"$document": "review_comments", "access": "read"},
        )
        self.assertEqual(
            merge["with"]["output_file"],
            {"$document": "review_comments", "access": "write"},
        )
        self.assertNotIn(
            "pending_file", steps["prepare_pending_review_comments"]["with"]
        )


if __name__ == "__main__":
    unittest.main()
