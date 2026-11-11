"""Unit tests for static validation safety and sanitized failure handling."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_examples as checker  # noqa: E402


class ExampleCheckerTests(unittest.TestCase):
    """Check synthetic authoring fixtures without launching an adapter."""

    def setUp(self) -> None:
        """Create a fresh synthetic public package tree."""
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.example = self.root / "sample"
        self.example.mkdir()

    def write(self, name: str, text: str) -> Path:
        """Write one fixture asset under the synthetic package."""
        path = self.example / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def flow(self, extra: str = "") -> Path:
        """Write a small pinned workflow for graph tests."""
        return self.write(
            "workflow.yaml",
            "schema: transist.flow.v1\nid: sample\nversion: 0.1.0\n"
            "plugins:\n  shell: 0.1.0\nsteps:\n  - id: echo\n"
            "    uses: process:shell/echo\n    with: {message: hello}\n" + extra,
        )

    def test_graph_pins_actions_and_assets(self) -> None:
        """A contained helper reference and exact action pin are accepted."""
        self.write("helper.py", "print('synthetic')\n")
        flow = self.flow("context: {helper: 'source://helper.py'}\n")
        _, pins, actions = checker.inspect_graph(flow)
        self.assertEqual(pins, {"shell": "0.1.0"})
        self.assertEqual(actions, ["process:shell/echo"])

    def test_word_logical_operators_are_rejected_in_control_expressions(self) -> None:
        """Reject unsupported operators before runtime can silently repeat a loop."""
        for field in ("until", "while", "guard"):
            block = "if" if field == "guard" else "loop"
            for operator in ("or", "and", "OR", "AND"):
                with self.subTest(field=field, operator=operator):
                    path = self.flow(
                        f"    {block}:\n      {field}: >-\n"
                        f"        steps.echo.out.passed == true {operator}\n"
                        '        steps.echo.out.done == "true"\n'
                    )
                    with self.assertRaisesRegex(
                        checker.CheckError, "unsupported logical operator"
                    ):
                        checker.inspect_graph(path)

    def test_symbolic_operators_and_quoted_words_are_accepted(self) -> None:
        """Operator checks ignore quoted text, escaped quotes, and path segments."""
        for expression in (
            'steps.echo.out.passed == true || steps.echo.out.done == "true"',
            'steps.echo.out.passed == true && steps.echo.out.done == "true"',
            'steps.echo.out.reason == "or and"',
            "steps.echo.out.reason == 'or and'",
            r'steps.echo.out.reason == "say \"or\" and wait"',
            'steps.echo.out.or == "true"',
            'steps.echo.out.and == "true"',
        ):
            with self.subTest(expression=expression):
                path = self.flow(
                    "    loop:\n      until: >-\n" + f"        {expression}\n"
                )
                checker.inspect_graph(path)

    def test_module_control_expressions_are_checked(self) -> None:
        """The same operator guard applies to declared package-local modules."""
        self.write(
            "module.yaml",
            "schema: transist.module.v1\nid: child\nversion: 0.1.0\n"
            "steps:\n  - id: repeat\n    control: control.noop\n"
            "    loop:\n      until: true or false\n",
        )
        with self.assertRaisesRegex(checker.CheckError, "unsupported logical operator"):
            checker.inspect_graph(self.flow("modules: {child: {path: module.yaml}}\n"))

    def test_duplicate_mapping_keys(self) -> None:
        """YAML cannot silently overwrite a pin or root identity."""
        path = self.write("bad.yaml", "id: first\nid: second\n")
        with self.assertRaisesRegex(checker.CheckError, "duplicate"):
            checker.load_yaml(path)

    def test_noncontiguous_control_refs_fail_before_runtime_commands(self) -> None:
        """A reused or misordered guard is not valid authored runtime control flow."""
        for block, field in (("loop", "body"), ("if", "then")):
            for refs in (["later", "guard"], ["guard"], ["echo", "guard", "later"]):
                with self.subTest(block=block, refs=refs):
                    sequence = "".join(f"        - ref: {ref}\n" for ref in refs)
                    path = self.flow(
                        "  - id: control\n    control: control.noop\n"
                        f"    {block}:\n      {field}:\n{sequence}"
                        "  - id: guard\n    control: control.noop\n"
                        "  - id: later\n    control: control.noop\n"
                    )
                    # A partial adjacent prefix is legal; only the referenced
                    # steps belong to this body, so cover it separately below.
                    if refs == ["guard"]:
                        checker.inspect_graph(path)
                        continue
                    with patch.object(checker, "runtime_command") as runtime:
                        with self.assertRaisesRegex(checker.CheckError, "contiguous"):
                            checker.validate_example(
                                self.example,
                                Path("/synthetic/transist"),
                                self.root,
                                self.root,
                            )
                        runtime.assert_not_called()

    def test_contiguous_guards_in_declared_modules_are_checked(self) -> None:
        """Recursive graph checks catch the same failure in a nested module body."""
        self.write(
            "module.yaml",
            "schema: transist.module.v1\nid: child\nversion: 0.1.0\nsteps:\n"
            "  - id: cycle\n    control: control.noop\n"
            "    loop:\n      body:\n        - ref: guard\n        - ref: capture\n"
            "  - id: capture\n    control: control.noop\n"
            "  - id: guard\n    control: control.noop\n",
        )
        path = self.flow("modules: {child: {path: module.yaml}}\n")
        with self.assertRaisesRegex(checker.CheckError, "contiguous"):
            checker.inspect_graph(path)

    def test_root_and_module_releases_are_exact_semver(self) -> None:
        """Root and module versions must be exact SemVer strings."""
        self.assertEqual(checker.inspect_graph(self.flow())[0]["version"], "0.1.0")
        for version in ("v1", "v2", "v12", "v0", "v01", "v2-extra", "1.01.0"):
            with self.subTest(version=version):
                path = self.flow()
                path.write_text(
                    path.read_text().replace("version: 0.1.0", f"version: {version}", 1)
                )
                with self.assertRaisesRegex(checker.CheckError, "workflow version"):
                    checker.inspect_graph(path)
        self.write(
            "child.yaml",
            "schema: transist.module.v1\nid: child\nversion: v2\nsteps: []\n",
        )
        path = self.flow("modules:\n  child: {path: child.yaml}\n")
        with self.assertRaisesRegex(checker.CheckError, "module version must be exact"):
            checker.inspect_graph(path)

    def test_parser_errors_are_sanitized(self) -> None:
        """Source lines are never propagated by the YAML loader."""
        path = self.write("bad.yaml", "fixture-private-marker: [unclosed")
        with self.assertRaises(checker.CheckError) as caught:
            checker.load_yaml(path)
        self.assertNotIn("fixture-private-marker", str(caught.exception))

    def test_inexact_pin_missing_pin_and_duplicate_steps(self) -> None:
        """Exempt negative pin fixtures; reject unpinned uses and duplicate steps."""
        for replacement in ("0.x", "latest", ">=0.1.0", "0.1.0-01"):
            path = self.flow()
            path.write_text(
                path.read_text().replace("shell: 0.1.0", f"shell: {replacement}")
            )
            with self.assertRaises(checker.CheckError):
                checker.inspect_graph(path)
        path = self.flow()
        path.write_text(path.read_text().replace("shell/echo", "absent/echo"))
        with self.assertRaisesRegex(checker.CheckError, "root plugin pin"):
            checker.inspect_graph(path)
        path = self.flow()
        path.write_text(path.read_text() + "  - id: echo\n    control: control.noop\n")
        with self.assertRaisesRegex(checker.CheckError, "duplicate step"):
            checker.inspect_graph(path)

    def test_asset_traversal_symlink_and_missing(self) -> None:
        """No module, prompt, or helper can escape its declaring directory."""
        self.write("helper.py", "pass\n")
        (self.example / "linked.py").symlink_to(self.example / "helper.py")
        for asset in (
            "../outside.py",
            "/etc/passwd",
            "linked.py",
            "missing.py",
            "{{inputs.file}}",
            "bad\x00asset.py",
            "bad\nasset.py",
        ):
            with self.assertRaises(checker.CheckError):
                checker.contained_file(self.example, asset)

    def test_declared_unused_modules_are_checked(self) -> None:
        """Declared modules must exist even when not invoked by current steps."""
        path = self.flow("modules:\n  unused: {path: missing.module.yaml}\n")
        with self.assertRaisesRegex(checker.CheckError, "missing"):
            checker.inspect_graph(path)

    def test_duplicate_module_identity_and_conflicting_pin(self) -> None:
        """Exempt the negative conflicting-pin fixture from catalog release policy."""
        for module in (
            "schema: transist.module.v1\nid: sample\nversion: 0.1.0\nsteps: []\n",
            "schema: transist.module.v1\nid: module\nversion: 0.1.0\n"
            "steps: []\nplugins: {shell: 2.0.0}\n",
        ):
            self.write("module.yaml", module)
            with self.assertRaises(checker.CheckError):
                checker.inspect_graph(
                    self.flow("modules: {child: {path: module.yaml}}\n")
                )

    def test_module_cycle(self) -> None:
        """Module recursion terminates with a clear error."""
        self.write(
            "module.yaml",
            "schema: transist.module.v1\nid: child\nversion: 0.1.0\n"
            "steps: []\nmodules: {self: {path: module.yaml}}\n",
        )
        with self.assertRaisesRegex(checker.CheckError, "cycle"):
            checker.inspect_graph(self.flow("modules: {child: {path: module.yaml}}\n"))

    def test_plugin_exact_identity_action_and_schema(self) -> None:
        """Exempt the negative manifest-pin mismatch fixture from release policy."""
        plugin = self.root / "plugins" / "shell"
        plugin.mkdir(parents=True)
        (plugin / "input.json").write_text('{"type":"object"}')
        (plugin / "output.json").write_text('{"type":"object"}')
        (plugin / "plugin.yaml").write_text(
            "schema: transist.plugin.v1\nid: shell\nversion: 0.1.0\n"
            "package: {files: [input.json, output.json]}\n"
            "adapter: process\nactions:\n  - name: echo\n"
            "    input_schema: input.json\n    output_schema: output.json\n"
        )
        self.assertEqual(
            len(
                checker.plugin_manifests(
                    self.root, {"shell": "0.1.0"}, ["process:shell/echo"]
                )
            ),
            1,
        )
        for pins, actions in (
            ({"shell": "2.0.0"}, []),
            ({"shell": "0.1.0"}, ["process:shell/absent"]),
            ({"shell": "0.1.0"}, ["mcp:shell/echo"]),
        ):
            with self.assertRaises(checker.CheckError):
                checker.plugin_manifests(self.root, pins, actions)
        (plugin / "input.json").write_text(
            '{"$ref": "https://example.org/remote-schema.json"}'
        )
        with patch.object(checker.subprocess, "run") as run:
            with self.assertRaisesRegex(checker.CheckError, "nonlocal schema"):
                checker.plugin_manifests(self.root, {"shell": "0.1.0"}, [])
            run.assert_not_called()

    def test_environment_has_no_inherited_credentials(self) -> None:
        """Only explicit OS basics are passed; user configuration is disposable."""
        with patch.dict(
            "os.environ",
            {
                "EXAMPLE_API_KEY": "dummy-validation-value",
                "TRANSIST_HOME": "private-fixture",
            },
        ):
            env = checker.isolated_environment(self.root)
        self.assertNotIn("EXAMPLE_API_KEY", env)
        self.assertNotIn("TRANSIST_HOME", env)
        self.assertTrue(Path(env["HOME"]).is_relative_to(self.root))

    def test_bound_sample_uses_synthetic_workspace(self) -> None:
        """Published placeholder paths are replaced only in disposable bound inputs."""
        sample = self.write(
            "inputs.example.yaml",
            "repo_path: /path/to/example\njira_ticket_id: PROJ-123\n",
        )
        path = checker.representative_inputs(
            self.example, self.root, {"inputs": {"repo_path": {}}}
        )
        inputs = json.loads(path.read_text())
        self.assertTrue(Path(inputs["repo_path"]).is_relative_to(self.root))
        self.assertEqual(
            sample.read_text(),
            "repo_path: /path/to/example\njira_ticket_id: PROJ-123\n",
        )
        self.assertEqual(inputs["jira_ticket_id"], "PROJ-123")

    def test_runtime_disallows_dispatch_and_live_readiness(self) -> None:
        """Guard against accidentally using run/start/installed check commands."""
        for args in (
            ["workflows", "run"],
            ["runs", "start"],
            ["plugins", "health"],
            ["workflows", "check", "--workflow", "sample@v1"],
        ):
            with patch.object(checker.subprocess, "run") as run:
                with self.assertRaisesRegex(checker.CheckError, "nonstatic"):
                    checker.runtime_command(
                        Path("/synthetic/transist"), args, self.root, {}, "fixture"
                    )
                run.assert_not_called()

    def test_bound_checks_allow_only_explicit_live_exclusions(self) -> None:
        """Only runtime-declared data dependencies defer; authority never does."""
        for status, code, allowed in (
            ("passed", "request_preparation", True),
            ("not_evaluated", "secret_value", True),
            ("not_evaluated", "external_state", True),
            ("not_evaluated", "request_preparation", False),
            ("not_evaluated", "required_input", False),
            ("warning", "input_schema", False),
            ("warning", "secret_value", False),
            ("deferred_to_dispatch", "step_output", True),
            ("deferred_to_dispatch", "mutable_variable", True),
            ("deferred_to_dispatch", "input_schema", True),
            ("deferred_to_dispatch", "deferred_to_dispatch", True),
            ("deferred_to_dispatch", "step_policy", False),
            ("deferred_to_dispatch", "secret_resolution", False),
            ("not_evaluated", "step_output", False),
        ):
            report = {"checks": [{"status": status, "code": code}]}
            result = subprocess.CompletedProcess(
                [], 0, json.dumps(report).encode(), b""
            )
            with self.subTest(status=status, code=code), patch.object(
                checker.subprocess, "run", return_value=result
            ):
                args = ["workflows", "check", "--path", "workflow.yaml"]
                if allowed:
                    checker.runtime_command(
                        Path("/synthetic/transist"), args, self.root, {}, "bound source"
                    )
                else:
                    with self.assertRaisesRegex(checker.CheckError, "incomplete"):
                        checker.runtime_command(
                            Path("/synthetic/transist"),
                            args,
                            self.root,
                            {},
                            "bound source",
                        )

    def test_runtime_failed_report_even_with_zero_exit_is_incomplete(self) -> None:
        """Do not turn missing secrets or any failed check into success."""
        for code in ("secret_resolution", "action_schema", "step_policy", "run_policy"):
            report = {
                "checks": [
                    {"status": "failed", "code": code, "message": "private-fixture"},
                    {"status": "deferred_to_dispatch", "code": "input_schema"},
                ]
            }
            result = subprocess.CompletedProcess(
                [], 0, json.dumps(report).encode(), b"private-fixture"
            )
            with patch.object(checker.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(checker.CheckError, "incomplete") as caught:
                    checker.runtime_command(
                        Path("/synthetic/transist"),
                        ["workflows", "check", "--path", "workflow.yaml"],
                        self.root,
                        {},
                        "bound",
                    )
            self.assertNotIn("private-fixture", str(caught.exception))

    def test_runtime_invalid_json_timeout_and_nonzero(self) -> None:
        """Malformed/failed subprocess responses remain sanitized failures."""
        responses = [
            subprocess.CompletedProcess([], 1, b"private-fixture", b"private-fixture"),
            subprocess.CompletedProcess([], 1, b"{}", b"private-fixture"),
            subprocess.CompletedProcess([], 0, b"[]", b""),
        ]
        for result in responses:
            with patch.object(checker.subprocess, "run", return_value=result):
                with self.assertRaises(checker.CheckError):
                    checker.runtime_command(
                        Path("/synthetic/transist"),
                        ["home", "init"],
                        self.root,
                        {},
                        "init",
                    )
        with patch.object(
            checker.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("private-fixture", 1),
        ):
            with self.assertRaisesRegex(checker.CheckError, "timed out"):
                checker.runtime_command(
                    Path("/synthetic/transist"), ["home", "init"], self.root, {}, "init"
                )

    def test_boundary_failure_reports_safe_code_and_fixed_hint(self) -> None:
        """Explain protected-root overlap without echoing native error paths."""
        report = {
            "valid": False,
            "checks": [
                {
                    "code": "filesystem_workspace_boundary",
                    "status": "failed",
                    "message": "external grant fixture-private-path "
                    "overlaps protected runtime root fixture-other-path",
                }
            ],
        }
        with patch.object(
            checker.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 1, json.dumps(report).encode(), b""
            ),
        ):
            with self.assertRaisesRegex(
                checker.CheckError, "scratch user grant"
            ) as caught:
                checker.runtime_command(
                    Path("/synthetic/transist"),
                    ["workflows", "check", "--path", "workflow.yaml"],
                    self.root,
                    {},
                    "bound",
                )
        self.assertIn("filesystem_workspace_boundary", str(caught.exception))
        self.assertNotIn("fixture-private-path", str(caught.exception))
        self.assertNotIn("fixture-other-path", str(caught.exception))

    def test_version_and_home_base(self) -> None:
        """Wrong versions and non-temporary homes fail before any validation."""
        binary = self.root / "transist"
        binary.write_text("fixture")
        binary.chmod(0o700)
        for output, code, success in (
            (b"transist 0.1.1\n", 0, True),
            (b"transist 0.1.0\n", 0, False),
            (b"transist 0.12.0\n", 0, False),
            (b"transist 0.11.0\n", 0, False),
            (b"transist 0.1.0-extra\n", 0, False),
            (b"transist 0.1.0\nadditional text\n", 0, False),
            (b"malformed", 0, False),
            (b"transist 0.1.0\n", 1, False),
            (b"transist 0.1.1-extra\n", 0, False),
            (b"transist 0.1.1\nadditional text\n", 0, False),
            (b"transist 0.1.1\n", 1, False),
        ):
            result = subprocess.CompletedProcess([], code, output, b"")
            with patch.object(checker.subprocess, "run", return_value=result):
                if success:
                    checker.check_version(binary)
                else:
                    with self.assertRaises(checker.CheckError):
                        checker.check_version(binary)
        self.assertEqual(checker.approved_home_base("/tmp"), Path("/tmp").resolve())
        for value in (".", "/", "/does-not-exist"):
            with self.assertRaises(checker.CheckError):
                checker.approved_home_base(value)

    def test_repository_tmp_home_base_is_explicit_and_nonsymlink(self) -> None:
        """Accept repo tmp storage, rejecting unrelated or symlinked bases."""
        repository = self.root.resolve() / "repository"
        repository.mkdir()
        approved = repository / "tmp"
        approved.mkdir()
        with patch.object(checker, "ROOT", repository):
            self.assertEqual(checker.approved_home_base(str(approved)), approved)
            child = approved / "approved-child"
            child.mkdir()
            self.assertEqual(checker.approved_home_base(str(child)), child)
            child.rmdir()
            with self.assertRaisesRegex(checker.CheckError, "unsafe components"):
                checker.approved_home_base(str(approved / ".." / "outside"))
            approved.rmdir()
            with self.assertRaises(checker.CheckError):
                checker.approved_home_base(str(approved))
        link = self.root.resolve() / "linked-repository"
        link.symlink_to(repository, target_is_directory=True)
        with patch.object(checker, "ROOT", link):
            with self.assertRaisesRegex(checker.CheckError, "nonsymlink"):
                checker.approved_home_base(str(link / "tmp"))
        with patch.object(checker, "ROOT", repository):
            approved.symlink_to(self.example.resolve(), target_is_directory=True)
            with self.assertRaisesRegex(checker.CheckError, "nonsymlink"):
                checker.approved_home_base(str(approved))
        # Repository storage was explicitly approved; arbitrary existing paths
        # outside the system temp tree are not approved by existence alone.
        with patch.object(Path, "is_dir", return_value=True):
            with self.assertRaises(checker.CheckError):
                checker.approved_home_base("/arbitrary-existing-directory")

    def test_sibling_tmp_keeps_evidence_outside_public_source(self) -> None:
        """Canonical sibling scratch is accepted without accepting symlink aliases."""
        repository = self.root.resolve() / "catalog"
        scratch = self.root.resolve() / "tmp"
        scratch.mkdir()
        with patch.object(checker, "ROOT", repository):
            self.assertEqual(checker.approved_home_base(str(scratch)), scratch)
            alias = scratch / "alias"
            alias.symlink_to(self.example.resolve(), target_is_directory=True)
            with self.assertRaisesRegex(checker.CheckError, "nonsymlink"):
                checker.approved_home_base(str(alias))

    def test_successful_static_report_and_plain_home_init(self) -> None:
        """Accept static status vocabulary and the init command's plain output."""
        responses = (
            (["home", "init"], b"initialized /tmp/synthetic-home\n"),
            (
                ["workflows", "check", "--path", "workflow.yaml"],
                json.dumps(
                    {
                        "validation": {
                            "checks": [
                                {"status": "passed"},
                                {"status": "not_evaluated", "code": "secret_value"},
                            ]
                        }
                    }
                ).encode(),
            ),
        )
        for args, output in responses:
            with patch.object(
                checker.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, output, b""),
            ):
                checker.runtime_command(
                    Path("/synthetic/transist"), args, self.root, {}, "fixture"
                )

    def test_empty_unknown_and_missing_checks_fail_closed(self) -> None:
        """Exit zero alone cannot establish static validation evidence."""
        for report in (
            {},
            {"checks": []},
            {"checks": [{"status": "unknown"}]},
            {"checks": [{"status": []}]},
        ):
            with patch.object(
                checker.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], 0, json.dumps(report).encode(), b""
                ),
            ):
                with self.assertRaisesRegex(checker.CheckError, "incomplete"):
                    checker.runtime_command(
                        Path("/synthetic/transist"),
                        ["workflows", "check", "--path", "workflow.yaml"],
                        self.root,
                        {},
                        "fixture",
                    )

    def test_missing_fourth_example_reports_incomplete(self) -> None:
        """Missing examples do not silently reduce the validation set."""
        examples = self.root / "examples"
        examples.mkdir()
        arguments = [
            "--transist",
            "/synthetic/transist",
            "--plugins-dir",
            str(self.root),
        ]
        with patch.object(checker, "ROOT", self.root), patch.object(
            checker, "check_version"
        ), patch.object(checker, "validate_example") as validate:
            import contextlib
            import io

            def refuse_missing(*args: object) -> None:
                """Simulate a missing workflow without making runtime calls."""
                raise checker.CheckError("missing asset")

            validate.side_effect = refuse_missing
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(checker.main(arguments), 1)
            self.assertEqual(validate.call_count, 4)
            self.assertEqual(output.getvalue().count("incomplete"), 4)

    def test_cleanup_actions_and_assets_are_checked(self) -> None:
        """Cleanup cannot introduce an unpinned action or an unchecked prompt asset."""
        path = self.flow("cleanup:\n  - id: tidy\n    uses: process:absent/echo\n")
        with self.assertRaisesRegex(checker.CheckError, "root plugin pin"):
            checker.inspect_graph(path)
        path = self.flow(
            "cleanup:\n  - id: tidy\n    uses: process:shell/echo\n"
            "    prompt_file: missing.md\n"
        )
        with self.assertRaisesRegex(checker.CheckError, "missing"):
            checker.inspect_graph(path)
        self.write("prompt.md", "Synthetic cleanup prompt.\n")
        path = self.flow(
            "cleanup:\n  - id: tidy\n    uses: process:shell/exec\n"
            "    prompt_file: prompt.md\n"
        )
        self.assertIn("process:shell/exec", checker.inspect_graph(path)[2])

    def test_module_only_step_ids_and_cleanup_duplicates(self) -> None:
        """Module-call IDs participate in uniqueness even without uses/control."""
        path = self.flow()
        path.write_text(path.read_text() + "  - id: echo\n    module: {ref: child}\n")
        with self.assertRaisesRegex(checker.CheckError, "duplicate step"):
            checker.inspect_graph(path)
        path = self.flow("cleanup:\n  - id: echo\n    control: control.noop\n")
        with self.assertRaisesRegex(checker.CheckError, "duplicate step"):
            checker.inspect_graph(path)

    def test_transitive_contained_schema_references_and_cycles(self) -> None:
        """Local refs may cross contained subdirectories, cycle, or use fragments."""
        a = self.write("schemas/a.json", '{"$ref":"../common.json#/$defs/item"}')
        self.write("common.json", '{"$defs":{"item":{"$ref":"schemas/a.json"}}}')
        checker.check_schema_graph(
            self.example, a, {"schemas/a.json", "common.json"}, set()
        )
        with self.assertRaisesRegex(checker.CheckError, "not selected"):
            checker.check_schema_graph(self.example, a, {"schemas/a.json"}, set())
        self.write("common.json", '{"$ref":"https://example.org/schema.json"}')
        with self.assertRaisesRegex(checker.CheckError, "nonlocal"):
            checker.check_schema_graph(
                self.example, a, {"schemas/a.json", "common.json"}, set()
            )

    def test_schema_reference_escape_symlink_and_missing(self) -> None:
        """Transitive refs cannot read outside package selection or follow symlinks."""
        self.write("target.json", "{}")
        (self.example / "linked.json").symlink_to(self.example / "target.json")
        for target in (
            "../outside.json",
            "%2e%2e/outside.json",
            "/etc/passwd",
            "linked.json",
            "missing.json",
            "//example.org/schema.json",
        ):
            schema = self.write("schema.json", json.dumps({"$ref": target}))
            with self.assertRaises(checker.CheckError):
                checker.check_schema_graph(
                    self.example, schema, {"schema.json", "linked.json"}, set()
                )

    def test_selected_payload_all_bytes_staged_source_unchanged(self) -> None:
        """Selected assets retain exact bytes/mode; unselected files stay out."""
        manifest = self.write(
            "plugin.yaml",
            "id: shell\npackage: {files: [plugin.py, schemas/a.json]}\n",
        )
        script = self.write("plugin.py", "#!/usr/bin/env python3\npass\n")
        script.chmod(0o755)
        schema = self.write("schemas/a.json", "{}")
        self.write("unselected.txt", "Not part of package.\n")
        scratch = self.root / "scratch"
        scratch.mkdir()
        staged = checker.stage_plugin(manifest, scratch, {})
        self.assertEqual(staged.read_bytes(), manifest.read_bytes())
        self.assertEqual(
            (staged.parent / "plugin.py").read_bytes(), script.read_bytes()
        )
        self.assertEqual(
            (staged.parent / "schemas/a.json").read_bytes(), schema.read_bytes()
        )
        self.assertTrue((staged.parent / "plugin.py").stat().st_mode & 0o111)
        self.assertFalse((staged.parent / "unselected.txt").exists())
        self.assertEqual(script.read_text(), "#!/usr/bin/env python3\npass\n")

    def test_missing_payload_is_not_fabricated(self) -> None:
        """Missing ordinary payloads and binary-looking assets fail before staging."""
        manifest = self.write("plugin.yaml", "id: shell\n")
        for files in ([], ["missing.py"], ["bin/other"], ["../outside"], ["a", "a"]):
            with self.assertRaises(checker.CheckError):
                checker.selected_payload(
                    manifest, {"id": "shell", "package": {"files": files}}
                )
        with self.assertRaisesRegex(checker.CheckError, "control characters"):
            checker.selected_payload(
                manifest, {"id": "shell", "package": {"files": ["bad\x00file"]}}
            )

    def ollama_fixture(self) -> Path:
        """Create a minimal source fixture for offline-build failure tests."""
        self.write("go.mod", "module ollama.cli\n\ngo 1.22\n")
        for filename in checker.OLLAMA_SOURCES:
            self.write(f"cmd/plugin/{filename}", "package main\n")
        return self.write(
            "plugin.yaml",
            "id: ollama.cli\nentrypoint: {command: bin/ollama.cli}\n"
            "package: {files: [bin/ollama.cli]}\n",
        )

    def test_only_documented_ollama_output_can_be_built(self) -> None:
        """No arbitrary missing executable or source output can trigger a build."""
        manifest = self.ollama_fixture()
        data = checker.load_yaml(manifest)
        self.assertEqual(checker.selected_payload(manifest, data), ["bin/ollama.cli"])
        data["entrypoint"]["command"] = "bin/other"
        with self.assertRaises(checker.CheckError):
            checker.selected_payload(manifest, data)
        data["entrypoint"]["command"] = "bin/ollama.cli"
        (self.example / "bin").symlink_to(self.root / "absent")
        with self.assertRaisesRegex(checker.CheckError, "unsafe"):
            checker.selected_payload(manifest, data)

    def test_stale_ollama_output_is_not_reused(self) -> None:
        """Ignored same-version executables cannot replace reviewed source builds."""
        manifest = self.ollama_fixture()
        self.write("bin/ollama.cli", "stale ignored executable")
        scratch = self.root / "scratch"
        scratch.mkdir()
        with patch.object(checker, "build_ollama") as build:
            staged = checker.stage_plugin(manifest, scratch, {})
        build.assert_called_once_with(
            self.example, staged.parent / "bin/ollama.cli", scratch, {}
        )
        self.assertFalse((staged.parent / "bin/ollama.cli").exists())

    def test_offline_build_failure_environment_and_no_source_mutation(self) -> None:
        """Go builds offline without credentials and writes only scratch paths."""
        self.ollama_fixture()
        scratch = self.root / "build-scratch"
        scratch.mkdir()
        env = checker.isolated_environment(scratch)
        output = scratch / "package" / "bin" / "ollama.cli"
        with patch.object(
            checker.shutil, "which", return_value="/synthetic/go"
        ), patch.object(
            checker.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 1, b"private fixture", b"private fixture"
            ),
        ) as run:
            with self.assertRaisesRegex(checker.CheckError, "build failed") as caught:
                checker.build_ollama(self.example, output, scratch, env)
        self.assertNotIn("private fixture", str(caught.exception))
        args = run.call_args.args[0]
        self.assertEqual(args[0], "/synthetic/go")
        self.assertIn("-mod=readonly", args)
        build_env = run.call_args.kwargs["env"]
        for key in ("GOPROXY", "GOSUMDB", "GOWORK", "GOENV"):
            self.assertEqual(build_env[key], "off")
        self.assertEqual(build_env["GOTOOLCHAIN"], "local")
        for key in ("GOCACHE", "GOTMPDIR", "GOPATH", "HOME", "TMPDIR"):
            self.assertTrue(Path(build_env[key]).is_relative_to(scratch))
        self.assertFalse((self.example / "bin").exists())
        self.assertFalse(output.exists())
        for filename in checker.OLLAMA_SOURCES:
            self.assertEqual(
                (scratch / "ollama-build/cmd/plugin" / filename).read_bytes(),
                (self.example / "cmd/plugin" / filename).read_bytes(),
            )
        self.assertEqual(
            (self.example / "go.mod").read_text(), "module ollama.cli\n\ngo 1.22\n"
        )

    def test_build_requires_go_and_stdlib_recipe(self) -> None:
        """Missing Go or changed recipes cannot fall back to fake binaries."""
        self.ollama_fixture()
        output = self.root / "out"
        with patch.object(checker.shutil, "which", return_value=None):
            with self.assertRaisesRegex(checker.CheckError, "Go executable"):
                checker.build_ollama(self.example, output, self.root, {"PATH": ""})
        self.write(
            "go.mod", "module ollama.cli\ngo 1.22\nrequire example.org/tool v1.0.0\n"
        )
        with patch.object(
            checker.shutil, "which", return_value="/synthetic/go"
        ), patch.object(checker.subprocess, "run") as run:
            with self.assertRaisesRegex(checker.CheckError, "stdlib-only"):
                checker.build_ollama(self.example, output, self.root, {"PATH": ""})
            run.assert_not_called()

    def test_process_policy_only_disposable_and_cursor_directory(self) -> None:
        """Change only process-delivery metadata, preserving other policy settings."""
        home = self.root / "home"
        home.mkdir()
        config = {
            "runtime": {"mode": "standalone"},
            "policy": {
                "profile": "permissive",
                "remote_secret_delivery": {
                    "process": False,
                    "http": False,
                    "mcp": False,
                },
            },
        }
        (home / "config.yaml").write_text(checker.yaml.safe_dump(config))
        checker.configure_static_home(home)
        updated = checker.load_yaml(home / "config.yaml")
        self.assertEqual(
            updated["policy"]["remote_secret_delivery"],
            {
                "process": True,
                "http": False,
                "mcp": False,
            },
        )
        self.assertEqual(updated["policy"]["profile"], "permissive")
        env = checker.isolated_environment(self.root)
        self.assertTrue((Path(env["HOME"]) / ".cursor").is_dir())

    def test_example_selection_does_not_require_unselected_roots(self) -> None:
        """Explicit selections ignore other roots but still fail when missing."""
        import contextlib
        import io

        examples = self.root / "examples"
        examples.mkdir()
        name = "edge_fault_advisory"
        (examples / name).mkdir()
        args = [
            "--transist",
            "/synthetic/transist",
            "--plugins-dir",
            str(self.root),
            "--example",
            name,
            "--example",
            name,
        ]
        with patch.object(checker, "ROOT", self.root), patch.object(
            checker, "check_version"
        ), patch.object(
            checker, "validate_example"
        ) as validate, contextlib.redirect_stdout(
            io.StringIO()
        ):
            self.assertEqual(checker.main(args), 0)
            self.assertEqual(validate.call_count, 1)
        args[-1] = "ai_agent_plugins_canary"
        with patch.object(checker, "ROOT", self.root), patch.object(
            checker, "check_version"
        ), patch.object(
            checker, "validate_example", side_effect=checker.CheckError("missing asset")
        ), contextlib.redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(checker.main(args), 1)


if __name__ == "__main__":
    unittest.main()
