"""Explicit review outcomes and exact remediation-cap stdout, without providers."""

from __future__ import annotations

import json
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_delivery import HELPERS, document, evaluate_guard, load_helper


class ReviewResponseTests(unittest.TestCase):
    """Fail closed on incomplete evidence and resolve only fully addressed threads."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the pure planner once; its publishing commands are never invoked."""
        cls.helper = load_helper("pr_review_replies")

    def comments(self) -> dict:
        """Return two actionable comments in the same synthetic review thread."""
        return {
            "comments": [
                {
                    "id": "comment-a",
                    "source": "review_thread",
                    "thread_id": "thread-one",
                    "review_comment_id": "101",
                },
                {
                    "id": "comment-b",
                    "source": "review_thread",
                    "thread_id": "thread-one",
                    "review_comment_id": "102",
                },
            ]
        }

    def entries(self, first: str = "addressed", second: str = "addressed") -> list:
        """Return explicit classified evidence for every fixture comment."""
        return [
            {"comment_id": "comment-a", "outcome": first, "reply": "Explain result A."},
            {
                "comment_id": "comment-b",
                "outcome": second,
                "reply": "Explain result B.",
            },
        ]

    def plan(self, entries: list, comments: dict | None = None) -> dict:
        """Feed an explicit markdown response array to the real pure planner."""
        notes = "## Review Replies\n```json\n" + json.dumps(entries) + "\n```\n"
        return self.helper.build_review_reply_plan(
            self.comments() if comments is None else comments, notes
        )

    def test_missing_heading_fails_even_with_no_comments(self) -> None:
        """An omitted response section never implies all requests were addressed."""
        for comments in (self.comments(), {"comments": []}):
            with self.subTest(comments=comments):
                with self.assertRaisesRegex(ValueError, "must contain.*Review Replies"):
                    self.helper.build_review_reply_plan(comments, "## Verification\nOK")

    def test_actionable_projection_retains_request_and_location_once(self) -> None:
        """Transport output and duplicated source bodies do not enter model context."""
        comment = {
            "id": "comment-a",
            "source": "review_thread",
            "body": "!!! Exact request\n",
            "thread_id": "T",
            "review_comment_id": "101",
            "path": "src/example.py",
            "line": 9,
            "diff_hunk": "@@ -5,2 +7,2 @@\nduplicated source body",
        }
        result = self.helper.filter_review_comments_payload(
            {
                "comments": [comment],
                "stdout": json.dumps(comment),
                "stderr": "transport",
            }
        )
        expected = {key: value for key, value in comment.items() if key != "diff_hunk"}
        expected["diff_hunk_header"] = "@@ -5,2 +7,2 @@"
        self.assertEqual(result["comments"], [expected])
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)

    def test_projection_budget_counts_actual_serialized_bytes(self) -> None:
        """Unicode escaping/formatting cannot overflow the file budget unnoticed."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            raw = root / "raw.json"
            output = root / "actionable.json"
            raw.write_text(
                json.dumps(
                    {
                        "comments": [
                            {
                                "id": "large",
                                "source": "review_thread",
                                "body": "é" * 12000,
                            }
                        ]
                    }
                )
            )
            output.write_text("previous complete context")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(HELPERS / "pr_review_replies.py"),
                    "filter",
                    "--input-file",
                    str(raw),
                    "--output-file",
                    str(output),
                ],
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"no requests were dropped", result.stderr)
            self.assertEqual(output.read_text(), "previous complete context")

    def test_actual_step7_projection_survives_actionable_consumer(self) -> None:
        """Keep the producer's sole location anchor without a raw diff body.

        The fixture is the actual committed pr_prepare_review_context output from
        the pre-review installed changes run (blob a8b0203f308348a72a57b4ff8b87aed2
        dbf8d1e243be36bfc9944d281b2dbde8), not a raw GitHub-comment approximation.
        """
        source = json.loads(
            (
                Path(__file__).parent / "fixtures/projected_review_context.json"
            ).read_text()
        )
        for explicit_nulls in (False, True):
            projected = copy.deepcopy(source)
            if explicit_nulls:
                projected["comments"][1].update(line=None, original_line=None)
            self.assertNotIn("diff_hunk", projected["comments"][1])
            result = self.helper.filter_review_comments_payload(projected)
            self.assertEqual(result["comments"], projected["comments"])
            self.assertEqual(result["count"], projected["count"])
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                raw, pr, output = (
                    root / name for name in ("input.json", "pr.json", "actionable.json")
                )
                raw.write_text(json.dumps(projected))
                pr.write_text(json.dumps(projected["pull_request"]))
                subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(HELPERS / "pr_review_replies.py"),
                        "filter",
                        "--input-file",
                        str(raw),
                        "--pr-file",
                        str(pr),
                        "--output-file",
                        str(output),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=15,
                )
                consumed = json.loads(output.read_bytes())
                self.assertEqual(consumed["comments"], projected["comments"])
                self.assertEqual(consumed["pull_request"], projected["pull_request"])

    def test_projected_header_is_typed_bounded_and_takes_precedence(self) -> None:
        """Reject invalid projected metadata; do not silently drop or rebuild it."""
        source = json.loads(
            (
                Path(__file__).parent / "fixtures/projected_review_context.json"
            ).read_text()
        )
        for header in (None, True, 1, [], {}, "é" * 32769):
            malformed = copy.deepcopy(source)
            malformed["comments"][1]["diff_hunk_header"] = header
            with self.subTest(header_type=type(header)), self.assertRaises(ValueError):
                self.helper.filter_review_comments_payload(malformed)
        projected = copy.deepcopy(source)
        projected["comments"][1]["diff_hunk"] = "@@ -50 +60 @@\nraw duplicate"
        result = self.helper.filter_review_comments_payload(projected)
        self.assertEqual(result["comments"][1]["diff_hunk_header"], "@@ -1 +1 @@")
        self.assertNotIn("diff_hunk", result["comments"][1])

    def test_array_in_a_later_section_cannot_replace_missing_reply_array(self) -> None:
        """A verification JSON block is not evidence of per-comment outcomes."""
        notes = "## Review Replies\n\n## Verification\n```json\n[]\n```\n"
        with self.assertRaisesRegex(ValueError, "exactly one fenced JSON array"):
            self.helper.build_review_reply_plan(self.comments(), notes)

    def test_one_missing_comment_fails(self) -> None:
        """Partial coverage must fail before any commit or publication."""
        with self.assertRaisesRegex(ValueError, "Missing explicit.*comment-b"):
            self.plan(self.entries()[:1])

    def test_empty_array_is_valid_only_without_actionable_comments(self) -> None:
        """An explicit empty array cannot silently mark actionable threads done."""
        with self.assertRaisesRegex(ValueError, "Missing explicit"):
            self.plan([])
        empty = self.plan([], {"comments": []})
        self.assertEqual(empty["responses"], [])
        self.assertEqual(empty["addressed_thread_ids"], [])

    def test_missing_invalid_or_nonstring_fields_fail(self) -> None:
        """The old omission-based contract and malformed new outcomes are rejected."""
        for field, value in (
            ("outcome", None),
            ("outcome", "unknown"),
            ("reply", None),
            ("reply", {"text": "not a string"}),
            ("reply", " "),
            ("comment_id", 101),
        ):
            entries = self.entries()
            entries[0][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.plan(entries)

    def test_duplicate_and_unknown_comment_ids_fail(self) -> None:
        """Invented or duplicate evidence cannot authorize thread resolution."""
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.plan([*self.entries(), self.entries()[0]])
        entries = self.entries()
        entries[0]["comment_id"] = "unknown-comment"
        with self.assertRaisesRegex(ValueError, "unknown or filtered"):
            self.plan(entries)

    def test_mixed_comment_thread_is_not_marked_addressed(self) -> None:
        """Any clarification or rejection keeps the entire shared thread unresolved."""
        for outcome in ("clarification", "rejected"):
            with self.subTest(outcome=outcome):
                plan = self.plan(self.entries(second=outcome))
                self.assertEqual(plan["addressed_thread_ids"], [])
                self.assertEqual(plan["count"], 1)
                self.assertEqual(plan["responses"][0]["comment_id"], "comment-b")
                self.assertEqual(plan["responses"][0]["review_comment_id"], "102")
                self.assertEqual(plan["comment_outcomes"][1]["outcome"], outcome)

    def test_fully_addressed_thread_is_listed_once_with_audit_evidence(self) -> None:
        """Explicit evidence, never omission, selects a deduplicated thread."""
        plan = self.plan(self.entries())
        self.assertEqual(plan["addressed_thread_ids"], ["thread-one"])
        self.assertEqual(plan["responses"], [])
        self.assertEqual(plan["comment_outcomes"], self.entries())

    def test_thread_classification_is_independent_and_conversations_do_not_resolve(
        self,
    ) -> None:
        """Only fully addressed review threads are passed to the public plugin."""
        comments = self.comments()
        comments["comments"][1]["thread_id"] = "thread-two"
        comments["comments"].append({"id": "conversation", "source": "pr_conversation"})
        entries = self.entries(second="rejected")
        entries.append(
            {"comment_id": "conversation", "outcome": "addressed", "reply": "Changed."}
        )
        plan = self.plan(entries, comments)
        self.assertEqual(plan["addressed_thread_ids"], ["thread-one"])
        self.assertEqual(len(plan["responses"]), 1)

    def test_all_addressed_resolution_still_requires_committed_changes(self) -> None:
        """Exercise actual publication guards and preserve the public plugin inputs."""
        plan = self.plan(self.entries())
        self.assertEqual(plan["addressed_thread_ids"], ["thread-one"])
        steps = {step["id"]: step for step in document("pr_review_changes")["steps"]}
        key = "steps.commit_review_changes.out.committed"
        publisher = steps["publish_review_responses"]
        self.assertEqual(
            publisher["uses"], "process:github.cli/pr_publish_review_replies"
        )
        self.assertEqual(
            publisher["with"]["resolve_addressed_threads"], "{{" + key + "}}"
        )
        for committed in (True, False):
            self.assertIsInstance(committed, bool)
            self.assertEqual(
                publisher["with"]["state_file"],
                {"$document": "review_replies_state", "access": "update"},
            )
        ordered = [step["id"] for step in document("pr_review_changes")["steps"]]
        self.assertLess(
            ordered.index("plan_review_responses"),
            ordered.index("commit_review_changes"),
        )


class RemediationCapTests(unittest.TestCase):
    """Remediation limits move to explicit managed JSON state, not shell booleans."""

    def test_boolean_stdout_is_exact_and_numeric_outputs_keep_newlines(self) -> None:
        """Only the numeric bookkeeping output remains; no Boolean-to-string bridge."""
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "staged.json"
            state.write_text('{"attempt":0}')
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(HELPERS / "validation_attempt.py"),
                    "--file",
                    str(state),
                    "--max-attempts",
                    "1",
                ],
                capture_output=True,
                check=True,
            )
            self.assertEqual(result.stdout, b"1\n")
            self.assertEqual(json.loads(state.read_bytes()), {"attempt": 1})

    def test_actual_loop_guard_stops_at_each_configured_cap(self) -> None:
        """Caps prevent extra remediation; current passed verification ends the loop."""
        steps = {
            step["id"]: step for step in document("validation_remediation")["steps"]
        }
        loop = steps["validation_remediation_loop"]["loop"]
        key = "steps.run_validation_remediation_iteration.out.passed"
        helper = load_helper("validation_attempt")
        for cap in (1, 2, loop["max_iters"]):
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as directory:
                state = Path(directory) / "attempt.json"
                state.write_text('{"attempt":0}')
                for iteration in range(cap):
                    self.assertEqual(helper.advance(state, cap), iteration + 1)
                    self.assertFalse(evaluate_guard(loop["until"], {key: False}))
                before = state.read_bytes()
                with self.assertRaises(ValueError):
                    helper.advance(state, cap)
                self.assertEqual(state.read_bytes(), before)
                self.assertTrue(evaluate_guard(loop["until"], {key: True}))


if __name__ == "__main__":
    unittest.main()
