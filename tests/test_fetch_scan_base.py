"""Offline checks of both contained Git fetch helpers and their trust boundary."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FetchScanBaseTests(unittest.TestCase):
    """Test declared branch selection without executing network operations."""

    def test_copies_and_authorized_fetches(self) -> None:
        """Only one exact tracking ref is updated, including a non-trunk PR base."""
        paths = [
            ROOT / "examples" / name / "modules/scripts/fetch_scan_base.py"
            for name in ("cursor_ticket_delivery", "hotfix_ticket_delivery")
        ]
        self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
        for path in paths:
            with self.subTest(path=path):
                spec = importlib.util.spec_from_file_location("fetch_base", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with tempfile.TemporaryDirectory(dir="/tmp") as temporary:
                    pr = Path(temporary) / "pr.json"
                    pr.write_text(
                        json.dumps({"pull_request": {"baseRefName": "release/1"}})
                    )
                    real_run = subprocess.run
                    calls = []

                    def offline(command: list[str], **kwargs: object) -> object:
                        """Run ref-format validation but intercept every fetch."""
                        calls.append(command)
                        if command[1] == "fetch":
                            return subprocess.CompletedProcess(command, 0)
                        if command[1] == "remote":
                            return subprocess.CompletedProcess(
                                command, 0, stdout="origin\n"
                            )
                        if command[1] == "rev-parse":
                            return subprocess.CompletedProcess(
                                command, 0, stdout=temporary
                            )
                        return real_run(command, **kwargs)

                    with patch.object(module.subprocess, "run", side_effect=offline):
                        module.fetch("origin", "release/1", str(pr))
                        self.assertEqual(
                            calls[-1],
                            [
                                "git",
                                "fetch",
                                "--no-tags",
                                "--no-recurse-submodules",
                                "--",
                                "origin",
                                "+refs/heads/release/1:refs/remotes/origin/release/1",
                            ],
                        )
                        for remote, branch, document in (
                            ("origin", "main", str(pr)),
                            ("--upload-pack=bad", "main", ""),
                            ("unknown", "main", ""),
                            ("origin", "../bad", ""),
                            ("origin", "-bad", ""),
                        ):
                            calls.clear()
                            with self.assertRaises(
                                (ValueError, subprocess.CalledProcessError)
                            ):
                                module.fetch(remote, branch, document)
                            self.assertFalse(any(call[1] == "fetch" for call in calls))
                        calls.clear()
                        pr.write_text('{"pull_request": {"baseRefName": "-malicious"}}')
                        with self.assertRaises(ValueError):
                            module.fetch("origin", "main", str(pr))
                        self.assertFalse(any(call[1] == "fetch" for call in calls))

                    def failed_fetch(command: list[str], **kwargs: object) -> object:
                        """Simulate a failed fetch while leaving validation local."""
                        if command[1] == "fetch":
                            raise subprocess.CalledProcessError(1, command)
                        if command[1] == "remote":
                            return subprocess.CompletedProcess(
                                command, 0, stdout="origin\n"
                            )
                        if command[1] == "rev-parse":
                            return subprocess.CompletedProcess(
                                command, 0, stdout=temporary
                            )
                        return real_run(command, **kwargs)

                    with patch.object(
                        module.subprocess, "run", side_effect=failed_fetch
                    ):
                        with self.assertRaises(subprocess.CalledProcessError):
                            module.fetch("origin", "main")
                    with module.fetch_lock(Path(temporary)):
                        with self.assertRaises(TimeoutError):
                            with module.fetch_lock(Path(temporary), timeout=0):
                                self.fail("overlapping fetch acquired the same lock")
                    with module.fetch_lock(Path(temporary), timeout=0):
                        pass
