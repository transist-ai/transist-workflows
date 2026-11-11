"""Root identity and attachment byte preservation in actual contained helpers."""

import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

EXAMPLE = Path(__file__).resolve().parents[1]


def load(path: str) -> object:
    """Load the example's own source asset without running its CLI."""
    spec = importlib.util.spec_from_file_location("helper", EXAMPLE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManagedDocumentTests(unittest.TestCase):
    """Files outside Git are data, with exact identity and bounded complete content."""

    def test_implementation_requires_explicit_approval_after_loop(self) -> None:
        """Exhaustion, rejection, missing and malformed decisions cannot publish."""
        helper = load("modules/scripts/require_implementation_approval.py")
        self.assertEqual(helper.main(["approved"]), 0)
        for args in (
            [],
            ["request_changes"],
            ["rejected"],
            ["Approved"],
            ["approved", "x"],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(
                io.StringIO()
            ) as err:
                self.assertEqual(helper.main(args), 1)
                self.assertIn("did not approve", err.getvalue())

    def test_root_metadata_identity_child_scope_and_duplicate_integrity(self) -> None:
        """Children share root identity and retain distinct exact gate identities."""
        ledger = load("modules/scripts/reviewer_context.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            metadata = root / "metadata.json"
            metadata.write_text('{"run":{"id":"root"}}')
            path = root / "staged.jsonl"
            ledger.initialize(path, metadata)
            record = {
                "schema": ledger.DECISION_SCHEMA,
                "run_id": "root__implementation",
                "gate_id": "review",
                "step_id": "review",
                "decision": "request_changes",
                "decided_at_ms": 1,
                "actor": "Reviewer",
                "reason": "  Exact\nfeedback  ",
            }
            self.assertTrue(ledger.capture(path, json.dumps(record)))
            metadata.write_text('{"run":{"id":"child"}}')
            self.assertFalse(ledger.capture(path, json.dumps(record)))
            self.assertTrue(
                ledger.capture(path, json.dumps({**record, "run_id": "root__pr"}))
            )
            records = ledger.history(path.read_bytes())
            self.assertEqual(records[0]["root_run_id"], "root")
            self.assertEqual(records[1], record)
            before = path.read_bytes()
            for change in (
                {"reason": "conflict"},
                {"decision": "approved"},
                {"actor": "other"},
            ):
                with self.assertRaises(ValueError):
                    ledger.capture(path, json.dumps({**record, **change}))
                self.assertEqual(path.read_bytes(), before)

    def test_root_identity_has_no_fallback_or_workspace_derived_id(self) -> None:
        """Missing/malformed metadata cannot create a prospective ledger."""
        ledger = load("modules/scripts/reviewer_context.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            metadata = root / "ticket-PROJ-123.json"
            for value in ({}, {"run": {}}, {"run": {"id": " "}}, {"run": {"id": 1}}):
                metadata.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    ledger.initialize(root / "output", metadata)
                self.assertFalse((root / "output").exists())

    def test_attachment_projection_is_lossless_and_paths_stay_relative(self) -> None:
        """Text, binary and manifest bytes survive staging relocation exactly."""
        helper = load("scripts/project_attachments.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            tree = root / "staged-tree"
            tree.mkdir()
            members = {
                "text.txt": "  caf\u00e9\r\n".encode(),
                "raw.bin": b"\x00\xff\n",
                "manifest.json": b'{"downloaded":[{"local_path":"text.txt"}]}',
            }
            for name, raw in members.items():
                (tree / name).write_bytes(raw)
            output = root / "context.json"
            helper.project(tree, output)
            payload = json.loads(output.read_bytes())
            self.assertEqual(
                {
                    name: base64.b64decode(raw)
                    for name, raw in payload["members"].items()
                },
                members,
            )
            self.assertNotIn(str(root), output.read_text())

    def test_projection_overflow_and_symlinks_do_not_replace_prior_output(self) -> None:
        """Oversized attachment context fails before a provider sees partial bytes."""
        helper = load("scripts/project_attachments.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            tree = root / "tree"
            tree.mkdir()
            output = root / "context.json"
            output.write_text("previous")
            large = tree / "large"
            large.write_bytes(b"x" * 65537)
            with self.assertRaises(ValueError):
                helper.project(tree, output)
            self.assertEqual(output.read_text(), "previous")
            large.unlink()
            (tree / "link").symlink_to(output)
            with self.assertRaises(ValueError):
                helper.project(tree, output)
            self.assertEqual(output.read_text(), "previous")


if __name__ == "__main__":
    unittest.main()
