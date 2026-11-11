"""Focused release-policy tests; invalid synthetic releases are explicit exemptions.

These negative fixtures are not maintained catalog assets. The validator must
reject them rather than provide a release-policy bypass.
"""

from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_examples as checker  # noqa: E402

# Exempt negative/version-policy fixtures, including the preceding release policy.
REJECTED_RELEASES = (
    "1.0.0",
    "v1",
    "v2",
    "0.0.0",
    "0.1.1",
    "0.2.0",
    "0.1.0-beta.1",
    "0.1.0+build.1",
    ">=0.1.0",
    "latest",
    "",
    None,
    1,
)


class VersionPolicyTests(unittest.TestCase):
    """Keep release versions distinct from schema and runtime identifiers."""

    def setUp(self) -> None:
        """Create an isolated graph and plugin payload under approved scratch."""
        temporary = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.flow = self.root / "workflow.yaml"
        self.child = self.root / "child.module.yaml"
        self.nested = self.root / "nested.module.yaml"
        self.plugin = self.root / "plugins" / "shell" / "plugin.yaml"
        self.plugin.parent.mkdir(parents=True)
        self.plugin.with_name("schema.json").write_text('{"type": "object"}\n')
        self.write(
            self.flow,
            {
                "schema": "transist.flow.v1",
                "id": "sample",
                "version": "0.1.0",
                "plugins": {"shell": "0.1.0"},
                "modules": {"child": {"path": self.child.name}},
                "steps": [{"id": "call", "module": {"ref": "child"}}],
            },
        )
        self.write(
            self.child,
            {
                "schema": "transist.module.v1",
                "id": "child",
                "version": "0.1.0",
                "plugins": {"shell": "0.1.0"},
                "modules": {"nested": {"path": self.nested.name}},
                "steps": [{"id": "echo", "uses": "process:shell/echo"}],
            },
        )
        self.write(
            self.nested,
            {
                "schema": "transist.module.v1",
                "id": "nested",
                "version": "0.1.0",
                "steps": [],
            },
        )
        self.write(
            self.plugin,
            {
                "schema": "transist.plugin.v1",
                "id": "shell",
                "version": "0.1.0",
                "adapter": "process",
                "package": {"files": ["schema.json"]},
                "actions": [
                    {
                        "name": "echo",
                        "input_schema": "schema.json",
                        "output_schema": "schema.json",
                    }
                ],
            },
        )

    def write(self, path: Path, document: dict) -> None:
        """Write synthetic metadata as YAML without modifying catalog sources."""
        path.write_text(yaml.safe_dump(document), encoding="utf-8")

    def test_fixed_release_accepts_nested_modules_and_exact_dependency(self) -> None:
        """0.1.0 graphs resolve module actions against the matching plugin payload."""
        root, pins, actions = checker.inspect_graph(self.flow)
        self.assertEqual(root["version"], "0.1.0")
        self.assertEqual(pins, {"shell": "0.1.0"})
        self.assertEqual(actions, ["process:shell/echo"])
        self.assertEqual(
            checker.plugin_manifests(self.root, pins, actions), [self.plugin]
        )
        self.assertEqual(checker.VERSION, "0.1.1")

    def test_root_rejects_other_releases(self) -> None:
        """Former policy, aliases, prereleases and malformed roots fail closed."""
        document = checker.load_yaml(self.flow)
        for version in REJECTED_RELEASES:
            with self.subTest(version=version):
                self.write(self.flow, {**document, "version": version})
                with self.assertRaisesRegex(checker.CheckError, "workflow.*version"):
                    checker.inspect_graph(self.flow)

    def test_declared_modules_reject_other_releases_recursively(self) -> None:
        """Both invoked and unused nested modules follow the same release policy."""
        for path in (self.child, self.nested):
            document = checker.load_yaml(path)
            for version in REJECTED_RELEASES:
                with self.subTest(module=path.name, version=version):
                    self.write(path, {**document, "version": version})
                    with self.assertRaisesRegex(checker.CheckError, "module.*version"):
                        checker.inspect_graph(self.flow)
            self.write(path, document)

    def test_root_and_module_pins_reject_other_releases(self) -> None:
        """An exact but disallowed pin cannot enter the aggregated graph."""
        for path in (self.flow, self.child):
            document = checker.load_yaml(path)
            for version in REJECTED_RELEASES:
                with self.subTest(document=path.name, version=version):
                    self.write(path, {**document, "plugins": {"shell": version}})
                    with self.assertRaisesRegex(checker.CheckError, "plugin pins"):
                        checker.inspect_graph(self.flow)
            self.write(path, document)

    def test_manifest_must_match_the_fixed_pin(self) -> None:
        """A valid graph cannot resolve to old or differently versioned bytes."""
        document = checker.load_yaml(self.plugin)
        for version in REJECTED_RELEASES:
            with self.subTest(version=version):
                self.write(self.plugin, {**document, "version": version})
                with self.assertRaisesRegex(checker.CheckError, "identity/version"):
                    checker.plugin_manifests(self.root, {"shell": "0.1.0"}, [])

    def test_matching_nonpolicy_manifest_and_pin_are_rejected(self) -> None:
        """Direct dependency validation cannot bypass policy with matching versions."""
        document = checker.load_yaml(self.plugin)
        for version in REJECTED_RELEASES:
            with self.subTest(version=version):
                self.write(self.plugin, {**document, "version": version})
                with self.assertRaisesRegex(checker.CheckError, "plugin version"):
                    checker.plugin_manifests(self.root, {"shell": version}, [])

    def test_schema_identifiers_are_not_release_versions(self) -> None:
        """Resetting releases cannot rename the v1 workflow/module formats."""
        for path, schema in (
            (self.flow, "transist.flow.0.1.0"),
            (self.child, "transist.module.0.1.0"),
        ):
            document = checker.load_yaml(path)
            self.write(path, {**document, "schema": schema})
            with self.subTest(schema=schema):
                with self.assertRaisesRegex(checker.CheckError, "schema"):
                    checker.inspect_graph(self.flow)
            self.write(path, document)

    def test_maintained_catalog_releases_modules_and_pins(self) -> None:
        """All four roots and every packaged module keep the 0.1.0/v1 distinction."""
        for name in sorted(checker.EXAMPLES):
            example = ROOT / "examples" / name
            checker.inspect_graph(example / "workflow.yaml")
            for path in [
                example / "workflow.yaml",
                *sorted((example / "modules").glob("*.module.yaml")),
            ]:
                with self.subTest(path=str(path.relative_to(ROOT))):
                    document = checker.load_yaml(path)
                    expected = (
                        "transist.flow.v1"
                        if path.name == "workflow.yaml"
                        else "transist.module.v1"
                    )
                    self.assertEqual(document["schema"], expected)
                    self.assertEqual(document["version"], "0.1.0")
                    for version in document.get("plugins", {}).values():
                        self.assertEqual(version, "0.1.0")


if __name__ == "__main__":
    unittest.main()
