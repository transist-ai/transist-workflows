"""Regression tests for publication boundaries, privacy, and inclusion enumeration."""

import contextlib
import io
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_public_snapshot as gate  # noqa: E402


class SnapshotTests(unittest.TestCase):
    """Exercise the gate using disposable text fixtures, never private repositories."""

    def setUp(self) -> None:
        """Create an isolated candidate tree."""
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name: str, content: bytes = b"public text\n") -> PurePosixPath:
        """Create one synthetic candidate file."""
        relative = PurePosixPath(name)
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return relative

    def check(self, name: str, content: bytes) -> list[str]:
        """Check a single synthetic candidate."""
        relative = self.put(name, content)
        return gate.check_file(self.root, relative, {relative})

    def test_public_allowlist(self) -> None:
        """Allow the agreed root files, future documents, and four example trees."""
        names = [
            "README.md",
            "CONTRIBUTING.md",
            "LICENSE",
            "NOTICE",
            ".gitignore",
            "requirements-dev.txt",
            "docs/compatibility.md",
            "docs/governed-use.md",
            "docs/validation.md",
            "docs/publication.md",
            "docs/history/compatibility-before-publication.md",
            "docs/history/revised-workflow-authoring-step-9.md",
            "docs/history/revised-workflow-authoring-step-10.md",
            "docs/history/revised-workflow-authoring-step-11.md",
            "docs/history/revised-workflow-authoring-step-12.md",
            ".github/workflows/validate.yml",
            "scripts/check.py",
            "tests/test_gate.py",
        ]
        names += [f"examples/{name}/inputs.example.yaml" for name in gate.EXAMPLES]
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(gate.path_allowed(PurePosixPath(name)))

    def test_reject_paths_before_any_read(self) -> None:
        """Disallowed paths cannot cause private-tree filesystem inspection."""
        names = [
            "private/README.md",
            "packages/README.md",
            "tmp/note.txt",
            ".git/config",
            "docs/other.md",
            "docs/history/other.md",
            "docs/revised-workflow-authoring-step-9.md",
            "other/file.py",
            "examples/unknown/workflow.yaml",
            "scripts/__pycache__/file.py",
            "scripts/.env",
            "scripts/.env.example",
            "scripts/run.log",
            "scripts/file.sig",
            "scripts/key.pem",
            "scripts/id.key",
            "scripts/inputs.yaml",
            "scripts/inputs.json",
            "scripts/inputs.local.yaml",
            "scripts/inputs.production.yml",
            "scripts/sample.inputs.yaml",
            "scripts/credentials.yaml",
            "scripts/id_rsa",
            "scripts/key.pub",
            "scripts/../private/file.py",
            "/scripts/file.py",
            "scripts/bad\nname.py",
            "scripts/node_modules/a.py",
            "tests/tmpfixture/output.md",
        ]
        with patch.object(
            Path, "lstat", side_effect=AssertionError("must not inspect")
        ):
            for name in names:
                with self.subTest(name=name):
                    errors = gate.check_file(self.root, PurePosixPath(name), set())
                    self.assertEqual(len(errors), 1)
                    self.assertNotIn(name, errors[0])

    def test_symlink_file_and_parent(self) -> None:
        """Neither a file symlink nor a symlinked ancestor may be followed."""
        self.put("README.md")
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "linked.py").symlink_to(self.root / "README.md")
        self.assertTrue(
            gate.check_file(self.root, PurePosixPath("scripts/linked.py"), set())
        )
        (self.root / "tests").symlink_to(
            self.root / "scripts", target_is_directory=True
        )
        self.assertTrue(
            gate.check_file(self.root, PurePosixPath("tests/linked.py"), set())
        )

    def test_deleted_and_nonregular_candidate(self) -> None:
        """Missing tracked files and directories fail closed."""
        self.assertTrue(gate.check_file(self.root, PurePosixPath("README.md"), set()))
        (self.root / "README.md").mkdir()
        self.assertTrue(gate.check_file(self.root, PurePosixPath("README.md"), set()))

    def test_binary_and_invalid_utf8(self) -> None:
        """Text-looking names do not admit binary bytes."""
        for content in (b"hello\x00world", b"\xff\xfe", b"hello\x1b[31m"):
            self.assertTrue(self.check("scripts/fixture.txt", content))

    def test_sensitive_categories_are_redacted(self) -> None:
        """Privacy findings reveal only categories and opaque candidate IDs."""
        fixtures = [
            b"su" + b"mup.example",
            b"andr" + b"ey",
            b"chern" + b"ykh",
            b"person@g" + b"mail.com",
            b"H" + b"B-1234",
            b"/Us" + b"ers/person/project",
            b"/ho" + b"me/person/project",
            b"hardware-" + b"backend",
            b"terminal-" + b"hub",
            b"ghp_" + b"x" * 30,
            b"sk-" + b"x" * 30,
            b"-----BEGIN PRIVATE " + b"KEY-----",
            b"api_key='" + b"x" * 32 + b"'",
            b"password: " + b"x" * 32,
            b'"password": "' + b"fictional-pass" + b'"',
            b"password: " + b"fakepass",
            b"https://fixture:" + b"fictional-pass@example.org",
            b"xox" + b"b-" + b"x" * 30,
            b"export EXAMPLE_API_KEY=" + b"fictionalpass123",
        ]
        for fixture in fixtures:
            with self.subTest(category=fixture[:2]):
                errors = self.check("README.md", fixture)
                self.assertTrue(errors)
                self.assertNotIn(fixture.decode(), "\n".join(errors))

    def test_metadata_secret_names_are_allowed(self) -> None:
        """Secret references, expressions, and placeholders are not literals."""
        for content in (
            b"secret_refs: [EXAMPLE_API_KEY]",
            b"api_key: ${EXAMPLE_API_KEY}",
            b"api_key: '{{inputs.api_key}}'",
            b"api_key: placeholder-value",
        ):
            self.assertFalse(self.check("README.md", content))

    def test_gate_and_tests_do_not_self_match(self) -> None:
        """The detector and its fixture source are safe publication candidates."""
        root = Path(__file__).resolve().parents[1]
        for name in (
            "scripts/check_public_snapshot.py",
            "scripts/check_examples.py",
            "tests/test_public_snapshot.py",
            "tests/test_check_examples.py",
        ):
            relative = PurePosixPath(name)
            self.assertEqual(gate.check_file(root, relative, {relative}), [])

    def test_sensitive_filename_is_not_disclosed(self) -> None:
        """Sensitive names fail even with clean bytes and stay out of diagnostics."""
        name = "scripts/andr" + "ey.py"
        relative = self.put(name)
        errors = gate.check_file(self.root, relative, {relative})
        self.assertTrue(errors)
        self.assertNotIn(name, "\n".join(errors))

    def test_safe_public_diagnostic_paths_are_actionable(self) -> None:
        """Safe public paths locate errors while source bytes remain redacted."""
        path = "scripts/public.py"
        errors = self.check(path, b"ghp_" + b"x" * 30)
        self.assertIn(path, errors[0])
        self.assertNotIn("x" * 30, errors[0])
        self.assertEqual(gate.location(PurePosixPath(path)), path)
        self.assertTrue(
            gate.location(PurePosixPath("private/hidden.md")).startswith("candidate-")
        )

    def test_relative_links_and_reference_links(self) -> None:
        """Contained files, directories, and reference links are checked."""
        readme = self.put(
            "README.md",
            b"[guide](docs/compatibility.md#pin)\n[guide][g]\n"
            b"[g]: docs/governed-use.md\n[folder](scripts/)\n"
            b"[web](https://example.org)\n",
        )
        paths = {
            readme,
            self.put("docs/compatibility.md"),
            self.put("docs/governed-use.md"),
            self.put("scripts/check.py"),
        }
        self.assertEqual(gate.check_file(self.root, readme, paths), [])

    def test_links_cannot_point_outside_snapshot(self) -> None:
        """No excluded-tree traversal, external file links, or raw diagnostics."""
        for target in (
            "private/hidden.md",
            "../escape.md",
            "%2e%2e/escape.md",
            "/etc/passwd",
            "missing.md",
            "file:///etc/passwd",
            "//example.org/x",
            "https://[invalid",
        ):
            readme = self.put("README.md", f"[link]({target})".encode())
            with patch.object(
                Path, "resolve", side_effect=AssertionError("must not resolve")
            ):
                errors = gate.check_file(self.root, readme, {readme})
            self.assertTrue(errors)
            self.assertNotIn(target, "\n".join(errors))

    def test_link_to_ignored_existing_file_fails(self) -> None:
        """Link targets must exist in the reviewed inclusion list."""
        self.put("docs/compatibility.md")
        relative = self.put("README.md", b"[doc](docs/compatibility.md)")
        self.assertTrue(gate.check_file(self.root, relative, {relative}))

    def test_enumeration_current_index_only(self) -> None:
        """Use the branch-independent index plus nonignored-untracked command."""
        result = subprocess.CompletedProcess(
            [], 0, b"README.md\0scripts/check.py\0README.md\0", b""
        )
        with patch.object(gate.subprocess, "run", return_value=result) as run:
            paths = gate.candidate_files(self.root)
        self.assertEqual(
            paths, [PurePosixPath("README.md"), PurePosixPath("scripts/check.py")]
        )
        self.assertEqual(
            run.call_args.args[0],
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        )

    def test_enumeration_failure_sanitized(self) -> None:
        """Subprocess failures never emit Git stderr or filenames."""
        with patch.object(
            gate.subprocess, "run", side_effect=OSError("sensitive fixture")
        ):
            with self.assertRaisesRegex(ValueError, "^candidate enumeration failed$"):
                gate.candidate_files(self.root)

    def test_list_is_all_or_nothing(self) -> None:
        """List output is emitted only after every candidate passes."""
        paths = [self.put("README.md"), PurePosixPath("private/hidden.md")]
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(gate, "ROOT", self.root), patch.object(
            gate, "candidate_files", return_value=paths
        ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(gate.main(["--list"]), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn("private/hidden.md", errors.getvalue())

    def test_list_success_is_sorted_inclusion(self) -> None:
        """Successful listing contains only reviewed relative names."""
        relative = self.put("README.md")
        output = io.StringIO()
        with patch.object(gate, "ROOT", self.root), patch.object(
            gate, "candidate_files", return_value=[relative]
        ), contextlib.redirect_stdout(output):
            self.assertEqual(gate.main(["--list"]), 0)
        self.assertEqual(output.getvalue(), "README.md\n")


if __name__ == "__main__":
    unittest.main()
