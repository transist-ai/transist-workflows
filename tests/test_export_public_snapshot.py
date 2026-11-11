"""Clean export integrity, failure isolation and unborn source provenance."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_public_snapshot as exporter  # noqa: E402
from source_identity import source_identity  # noqa: E402


class ExportTests(unittest.TestCase):
    """Use small real repositories, not mocked Git/index success."""

    def setUp(self) -> None:
        """Create owned, canonical scratch and a template-free unborn source."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "source"
        self.root.mkdir()
        self.destination = self.base / "candidate"
        self.git(self.root, "init", "--quiet", "--initial-branch=main", "--template=")
        (self.root / "README.md").write_bytes(b"# Example\r\nExact bytes.\n")
        (self.root / "scripts").mkdir()
        (self.root / "scripts/helper.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.root / "scripts/helper.sh").chmod(0o755)

    def git(self, root: Path, *arguments: str) -> bytes:
        """Invoke bounded Git metadata operations with captured output."""
        return subprocess.run(
            ["git", *arguments], cwd=root, capture_output=True, check=True, timeout=30
        ).stdout

    def test_unborn_export_exact_bytes_modes_and_empty_history(self) -> None:
        """Stage exact CRLF bytes and executable mode without refs, hooks or commits."""
        receipt = exporter.export_snapshot(self.root, self.destination, True)
        report = json.loads(receipt.read_text())
        self.assertIsNone(report["source"]["head"])
        self.assertEqual(report["sha256"], source_identity(self.destination)["sha256"])
        self.assertEqual(self.git(self.destination, "for-each-ref"), b"")
        self.assertEqual(self.git(self.destination, "remote"), b"")
        self.assertFalse((self.destination / ".git/hooks").exists())
        self.assertEqual(
            self.git(self.destination, "symbolic-ref", "HEAD"), b"refs/heads/main\n"
        )
        for record in report["files"]:
            path = record["path"]
            self.assertEqual(
                self.git(self.destination, "show", ":" + path),
                (self.root / path).read_bytes(),
            )
            self.assertEqual(
                (self.destination / path).stat().st_mode & 0o777,
                (self.root / path).stat().st_mode & 0o777,
            )

    def test_existing_nested_and_symlink_destination_rejected(self) -> None:
        """Never overwrite a directory or place an export inside its own source."""
        self.destination.mkdir()
        for destination in (self.destination, self.root / "nested"):
            with self.assertRaises(ValueError):
                exporter.export_snapshot(self.root, destination)
        alias = self.base / "alias"
        alias.symlink_to(self.destination, target_is_directory=True)
        with self.assertRaises(ValueError):
            exporter.export_snapshot(self.root, alias)

    def test_ignored_private_trees_never_exported(self) -> None:
        """Ignored private data and source Git history never enter the candidate."""
        (self.root / ".gitignore").write_text("priv/\npackages/\ntmp/\n")
        for name in ("priv", "packages", "tmp"):
            (self.root / name).mkdir()
            (self.root / name / "data.txt").write_text("excluded fixture\n")
        exporter.export_snapshot(self.root, self.destination)
        self.assertEqual(
            {p.name for p in self.destination.iterdir()},
            {"README.md", "scripts", ".gitignore"},
        )

    def test_symlink_and_special_source_refused(self) -> None:
        """Allowed names cannot smuggle symlinks or block on FIFO reads."""
        path = self.root / "scripts/unsafe.txt"
        path.write_text("tracked candidate\n")
        self.git(self.root, "add", "scripts/unsafe.txt")
        path.unlink()
        for kind in ("symlink", "fifo"):
            if kind == "symlink":
                path.symlink_to(self.root / "README.md")
            else:
                os.mkfifo(path)
            with self.assertRaises(ValueError):
                exporter.export_snapshot(self.root, self.destination)
            self.assertFalse(self.destination.exists())
            path.unlink()

    def test_missing_indexed_source_refused(self) -> None:
        """Missing tracked files are errors rather than silently dropped candidates."""
        self.git(self.root, "add", "README.md")
        (self.root / "README.md").unlink()
        with self.assertRaises(ValueError):
            exporter.export_snapshot(self.root, self.destination)

    def test_mutation_during_copy_has_no_approved_receipt(self) -> None:
        """Post-copy mutation invalidates the result even if Git staging succeeds."""
        stage = exporter.stage_verified

        def mutate(destination: Path, expected: dict) -> None:
            """Stage faithfully, then simulate concurrent source editing."""
            stage(destination, expected)
            (self.root / "README.md").write_text("changed\n")

        with patch.object(exporter, "stage_verified", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "source changed"):
                exporter.export_snapshot(self.root, self.destination, True)
        self.assertFalse(self.destination.with_suffix(".inventory.json").exists())

    def test_copied_validation_failure_has_no_approved_receipt(self) -> None:
        """Copied-content rejection never emits an approved inventory."""
        check = exporter.check_file

        def reject(root: Path, path: Path, paths: set) -> list[str]:
            """Reject only the copied destination to exercise the second gate."""
            return (
                ["fixture rejection"]
                if root == self.destination
                else check(root, path, paths)
            )

        with patch.object(exporter, "check_file", side_effect=reject):
            with self.assertRaisesRegex(ValueError, "copied publication"):
                exporter.export_snapshot(self.root, self.destination, True)
        self.assertFalse(self.destination.with_suffix(".inventory.json").exists())
        self.assertFalse((self.destination / ".git").exists())

    def test_git_transformations_do_not_change_export(self) -> None:
        """Inherited Git config cannot alter bytes or inject template hooks."""
        with patch.dict(
            os.environ,
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.autocrlf",
                "GIT_CONFIG_VALUE_0": "true",
                "GIT_TEMPLATE_DIR": str(self.root),
            },
        ):
            exporter.export_snapshot(self.root, self.destination, True)
        self.assertEqual(
            self.git(self.destination, "show", ":README.md"),
            (self.root / "README.md").read_bytes(),
        )

    def test_index_content_and_mode_mismatch_fail_closed(self) -> None:
        """Real staging must reject either a different blob or executable mode."""
        for index, expected in enumerate(
            ((b"different\n", 0o644), (b"actual\n", 0o755))
        ):
            target = self.base / f"index-{index}"
            target.mkdir()
            (target / "README.md").write_bytes(b"actual\n")
            (target / "README.md").chmod(0o644)
            with self.assertRaisesRegex(ValueError, "indexed bytes/modes differ"):
                exporter.stage_verified(target, {Path("README.md"): expected})


if __name__ == "__main__":
    unittest.main()
