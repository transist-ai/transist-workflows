"""Keep implementation-loop exhaustion from authorizing downstream delivery."""

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest


class ImplementationApprovalTests(unittest.TestCase):
    """Only the runtime gate's exact approved outcome may advance the workflow."""

    def test_require_approval(self) -> None:
        """Missing, rejected, request-changes and malformed decisions fail closed."""
        path = (
            Path(__file__).resolve().parents[1]
            / "modules/scripts/require_implementation_approval.py"
        )
        spec = importlib.util.spec_from_file_location("approval", path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
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


if __name__ == "__main__":
    unittest.main()
