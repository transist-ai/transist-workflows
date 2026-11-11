"""Regressions for the static-only automatic entrypoint."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_static as checker  # noqa: E402


class StaticTests(unittest.TestCase):
    """Source inspection cannot silently become helper or runtime execution."""

    def test_exact_inventory_parses_without_subprocess(self) -> None:
        """All seven real graphs pass without any tool dispatch during parsing."""
        paths = [Path(p) for p in checker.candidate_files(ROOT)]
        with patch.object(checker.subprocess, "run", side_effect=AssertionError):
            checker.inspect_source(ROOT, paths)

    def test_source_is_data_not_imported(self) -> None:
        """A top-level trap is parsed, never executed; missing graphs still fail."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "trap.py").write_text("raise RuntimeError('must not execute')\n")
            (root / "examples").mkdir()
            with self.assertRaisesRegex(ValueError, "inventory drift"):
                checker.inspect_source(root, [Path("trap.py")])

    def test_only_static_tools_and_exact_shell_paths(self) -> None:
        """No unittest, Go, plugin installer, runtime or helper is an entrypoint."""
        commands = checker.commands([Path("a.py"), Path("scripts/a.sh")], Path("/tmp"))
        self.assertEqual(
            [command[0] for command in commands],
            [sys.executable, sys.executable, "shellcheck", "actionlint", "gitleaks"],
        )
        self.assertEqual(commands[0][1:4], ["-m", "black", "--check"])
        self.assertEqual(commands[1][1:3], ["-m", "flake8"])
        self.assertEqual(commands[2], ["shellcheck", "scripts/a.sh"])
        self.assertFalse(any("*" in argument for c in commands for argument in c))

    def test_missing_selected_root_fails(self) -> None:
        """Untracked/ignored roots cannot disappear from the published graph set."""
        paths = [Path(p) for p in checker.candidate_files(ROOT)]
        paths.remove(Path("examples/edge_fault_advisory/workflow.yaml"))
        with self.assertRaisesRegex(ValueError, "absent from approved inventory"):
            checker.inspect_source(ROOT, paths)


if __name__ == "__main__":
    unittest.main()
