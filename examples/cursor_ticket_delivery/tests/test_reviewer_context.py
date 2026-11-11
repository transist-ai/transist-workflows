"""Managed-ledger identity, scope, integrity and bounded-history regressions.

The runtime owns private-copy locking/atomic publication; these converted tests
retain the old decision-validation/dedup/bounds coverage at the new data contract.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "modules/scripts/reviewer_context.py"


def decision(**changes: object) -> dict:
    """Build exact synthetic child-gate evidence with controllable fields."""
    return {
        "schema": "transist.gate_decision.v1",
        "run_id": "root__child",
        "gate_id": "review",
        "step_id": "review_step",
        "decision": "request_changes",
        "actor": "R\u00e9viseur",
        "actor_source": "flag",
        "decided_at_ms": 1000,
        "reason": "  Keep the boundary.\n\u4fdd\u7559\u5c65\u6b74 \U0001f9ea  ",
        **changes,
    }


class ReviewerContextTests(unittest.TestCase):
    """Test real staged paths outside the workspace; never access runtime storage."""

    def setUp(self) -> None:
        """Initialize a fresh root-only fixture from actual metadata shape."""
        spec = importlib.util.spec_from_file_location("reviewer_context", HELPER)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.metadata = self.root / "metadata.json"
        self.metadata.write_text('{"runtime":{"version":"0.1.1"},"run":{"id":"root"}}')
        self.path = self.root / "private-stage/ledger.jsonl"
        self.helper.initialize(self.path, self.metadata)

    def capture(self, value: object) -> bool:
        """Send a synthetic bound record through the actual helper's validator."""
        return self.helper.capture(self.path, json.dumps(value, ensure_ascii=False))

    def assert_invalid(self, value: object) -> None:
        """Invalid evidence cannot partially alter prior complete history."""
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.capture(value)
        self.assertEqual(before, self.path.read_bytes())

    def test_metadata_identity_exact_shared_and_exclusive(self) -> None:
        """Children retain root identity, independent of paths and ticket values."""
        self.assertEqual(
            self.helper.history(self.path.read_bytes())[0],
            {"schema": "transist.reviewer_context.v1", "root_run_id": "root"},
        )
        self.metadata.write_text('{"run":{"id":"root__other-child"}}')
        self.assertTrue(self.capture(decision()))
        self.assertTrue(self.capture(decision(run_id="root__second-child")))
        self.assertEqual(
            self.helper.history(self.path.read_bytes())[0]["root_run_id"], "root"
        )
        with self.assertRaises(FileExistsError):
            self.helper.initialize(self.path, self.metadata)

    def test_missing_malformed_identity_fails_before_file_creation(self) -> None:
        """No fallback identity, including duplicate JSON keys or whitespace IDs."""
        for value in (
            {},
            None,
            [],
            {"run": None},
            {"run": {}},
            *(
                {"run": {"id": bad}}
                for bad in (None, 1, True, [], "", " ", " root", "x\n")
            ),
        ):
            with self.subTest(value=value):
                self.metadata.write_text(json.dumps(value))
                output = self.root / "never-created.jsonl"
                with self.assertRaises(ValueError):
                    self.helper.initialize(output, self.metadata)
                self.assertFalse(output.exists())
        for raw in ('{"run":{"id":"a","id":"b"}}', "{", "\ufffd"):
            self.metadata.write_text(raw)
            with self.assertRaises(ValueError):
                self.helper.root_identity(self.metadata)

    def test_exact_history_actor_chronology_and_duplicate_resume(self) -> None:
        """Approvals/rejections never erase prior requests or normalize exact text."""
        records = [
            decision(),
            decision(decision="approved", decided_at_ms=2000),
            decision(decision="rejected", decided_at_ms=3000),
        ]
        for record in records:
            self.assertTrue(self.capture(record))
        self.assertEqual(self.helper.history(self.path.read_bytes())[1:], records)
        before = self.path.read_bytes()
        self.assertFalse(self.capture(dict(reversed(list(records[0].items())))))
        self.assertFalse(self.helper.capture(self.path, None))
        self.assertEqual(self.path.read_bytes(), before)
        for key, value in (
            ("actor", "other"),
            ("reason", "replacement"),
            ("decision", "approved"),
        ):
            self.assert_invalid({**records[0], key: value})

    def test_every_identity_component_distinguishes_gates(self) -> None:
        """Root/child scope, gate, step and timestamp distinguish decisions."""
        records = [
            decision(),
            decision(run_id="root__second"),
            decision(gate_id="another"),
            decision(step_id="another"),
            decision(decided_at_ms=1001),
        ]
        for record in records:
            self.assertTrue(self.capture(record))
        self.assertEqual(self.helper.history(self.path.read_bytes())[1:], records)

    def test_all_schema_types_required_fields_and_malformed_records(self) -> None:
        """Retain strict complete records, not truthy or partly reconstructed input."""
        for key in (
            "schema",
            "run_id",
            "gate_id",
            "step_id",
            "decision",
            "decided_at_ms",
        ):
            invalid = decision()
            del invalid[key]
            self.assert_invalid(invalid)
        for key, value in (
            ("schema", "wrong"),
            ("run_id", None),
            ("gate_id", 1),
            ("step_id", " "),
            ("decision", "approve"),
            ("decision", []),
            ("decided_at_ms", True),
            ("decided_at_ms", -1),
            ("decided_at_ms", "1000"),
            ("actor", None),
            ("actor_source", []),
            ("reason", {}),
            ("extra", "unknown"),
        ):
            with self.subTest(key=key, value=value):
                self.assert_invalid(decision(**{key: value}))
        for value in (None, [], "approved", True, 42):
            self.assert_invalid(value)
        for raw in ("{", '{"schema":1,"schema":2}'):
            with self.assertRaises(ValueError):
                self.helper.capture(self.path, raw)

    def test_review_scope_and_exact_revision_metadata_are_retained(self) -> None:
        """The review request belongs to the same child gate and is never discarded."""
        revision = {
            "schema": "transist.document_revision.v1",
            "revision_id": "exact-revision",
            "document": "plan",
            "blob": {"sha256": "a" * 64},
        }
        request = {
            "schema": "transist.gate_review_request.v1",
            "run_id": "root__child",
            "gate_id": "review",
            "step_id": "review_step",
            "execution": 1,
            "review_documents": [revision],
        }
        record = decision(review_request=request)
        self.assertTrue(self.capture(record))
        self.assertEqual(self.helper.history(self.path.read_bytes())[1], record)
        self.assertTrue(
            self.capture(
                decision(
                    decided_at_ms=2001, review_request={**request, "execution": 1.0}
                )
            )
        )
        for extra in (
            {"run_id": "wrong"},
            {"execution": True},
            {"review_documents": None},
            {"review_documents": [{}]},
        ):
            self.assert_invalid(
                decision(decided_at_ms=2000, review_request={**request, **extra})
            )

    def test_decision_byte_limits_never_drop_history(self) -> None:
        """128 records fit; duplicates at the cap and complete byte bounds hold."""
        for number in range(128):
            self.capture(decision(decided_at_ms=number, reason=""))
        self.assertFalse(self.capture(decision(decided_at_ms=127, reason="")))
        self.assert_invalid(decision(decided_at_ms=128))
        self.path.write_bytes(
            self.helper._encode(
                {"schema": self.helper.CONTEXT_SCHEMA, "root_run_id": "root"}
            )
        )
        self.assert_invalid(decision(reason="\u00e9" * 40000))
        self.path.write_bytes(b"x" * 65537)
        with self.assertRaises(ValueError):
            self.helper.capture(self.path, None)

    def test_corrupt_stored_history_and_missing_path_fail_closed(self) -> None:
        """Absence of current feedback never repairs corrupt prior evidence."""
        header = self.path.read_bytes()
        for raw in (
            b"",
            b"{",
            b"null\n",
            header + b"null\n",
            header + b"\xff\n",
            header + self.helper._encode(decision()) * 2,
        ):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.helper.capture(self.path, None)
            self.assertEqual(self.path.read_bytes(), raw)
        self.path.unlink()
        with self.assertRaises(ValueError):
            self.helper.capture(self.path, None)

    def test_symlinks_traversal_and_relative_paths_are_rejected(self) -> None:
        """A staged path is data; no target-workspace restriction or path guessing."""
        link = self.root / "link"
        link.symlink_to(self.path)
        for path in (link, Path("relative"), self.root / ".." / "outside"):
            with self.assertRaises(ValueError):
                self.helper.capture(path, None)

    def test_cli_ignores_child_metadata_and_does_not_print_feedback(self) -> None:
        """Process boundaries keep shared identity and exact feedback without leaks."""
        self.metadata.write_text('{"run":{"id":"child-not-root"}}')
        env = {
            "PATH": os.defpath,
            "TRANSIST_RUNTIME_METADATA_FILE": str(self.metadata),
            "TRANSIST_GATE_DECISION_JSON": json.dumps(decision()),
        }
        for _ in range(2):
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(HELPER),
                    "capture",
                    "--file",
                    str(self.path),
                ],
                env=env,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
        records = self.helper.history(self.path.read_bytes())
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["root_run_id"], "root")


if __name__ == "__main__":
    unittest.main()
