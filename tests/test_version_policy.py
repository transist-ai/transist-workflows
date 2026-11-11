"""Exact independent SemVer policy tests using synthetic graph fixtures."""

from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_examples as checker  # noqa: E402

VALID_RELEASES = (
    "0.0.0",
    "1.2.3",
    "999999999999999999999.2.3",
    "1.0.0-alpha",
    "1.0.0-alpha.0.1",
    "1.0.0-01a",
    "1.0.0--",
    "1.0.0+001",
    "1.0.0-rc.1+build.001-x",
    "1.0.0+abc-def.000",
)
INVALID_RELEASES = (
    "",
    None,
    1,
    True,
    "v1.2.3",
    "V1.2.3",
    "1.2",
    "1.2.3.4",
    "01.2.3",
    "1.02.3",
    "1.2.03",
    "1.2.3-01",
    "1.2.3-a.00",
    "1.2.3-",
    "1.2.3+",
    "1.2.3-.a",
    "1.2.3-a..b",
    "1.2.3-a.",
    "1.2.3+.a",
    "1.2.3+a..b",
    "1.2.3+a.",
    "1.2.3+a+b",
    "1.2.3-a_b",
    "1.2.3+build_1",
    "1.2.3-ä",
    "1.٢.3",
    ">=1.2.3",
    "^1.2.3",
    "1.2.x",
    "latest",
    " 1.2.3",
    "1.2.3\n",
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

    def test_independent_releases_and_exact_dependency(self) -> None:
        """Root, nested modules and plugin can all use different SemVer releases."""
        for path, version in (
            (self.flow, "2.0.0"),
            (self.child, "3.0.0-rc.1"),
            (self.nested, "4.2.0+build.01"),
        ):
            document = checker.load_yaml(path)
            self.write(path, {**document, "version": version})
        for path in (self.flow, self.child):
            document = checker.load_yaml(path)
            self.write(path, {**document, "plugins": {"shell": "5.0.0-beta+001"}})
        manifest = checker.load_yaml(self.plugin)
        self.write(self.plugin, {**manifest, "version": "5.0.0-beta+001"})
        root, pins, actions = checker.inspect_graph(self.flow)
        self.assertEqual(root["version"], "2.0.0")
        self.assertEqual(pins, {"shell": "5.0.0-beta+001"})
        self.assertEqual(actions, ["process:shell/echo"])
        self.assertEqual(
            checker.plugin_manifests(self.root, pins, actions), [self.plugin]
        )
        self.assertEqual(checker.VERSION, "0.1.1")

    def test_valid_versions_in_every_position(self) -> None:
        """Accept valid SemVer at each graph and dependency boundary."""
        for version in VALID_RELEASES:
            with self.subTest(version=version):
                for path in (self.flow, self.child, self.nested):
                    document = checker.load_yaml(path)
                    self.write(path, {**document, "version": version})
                    checker.inspect_graph(self.flow)
                    self.write(path, document)
                originals = [
                    checker.load_yaml(path)
                    for path in (self.flow, self.child, self.plugin)
                ]
                for path, document in zip((self.flow, self.child), originals):
                    self.write(path, {**document, "plugins": {"shell": version}})
                self.write(self.plugin, {**originals[2], "version": version})
                _, pins, actions = checker.inspect_graph(self.flow)
                self.assertEqual(
                    checker.plugin_manifests(self.root, pins, actions), [self.plugin]
                )
                for path, document in zip(
                    (self.flow, self.child, self.plugin), originals
                ):
                    self.write(path, document)

    def test_invalid_versions_in_every_position(self) -> None:
        """Malformed releases fail at roots, recursive modules, pins, and manifests."""
        for version in INVALID_RELEASES:
            with self.subTest(version=version):
                for path in (self.flow, self.child, self.nested):
                    document = checker.load_yaml(path)
                    self.write(path, {**document, "version": version})
                    with self.assertRaisesRegex(checker.CheckError, "version"):
                        checker.inspect_graph(self.flow)
                    self.write(path, document)
                for path in (self.flow, self.child):
                    document = checker.load_yaml(path)
                    self.write(path, {**document, "plugins": {"shell": version}})
                    with self.assertRaisesRegex(checker.CheckError, "plugin pins"):
                        checker.inspect_graph(self.flow)
                    self.write(path, document)
                manifest = checker.load_yaml(self.plugin)
                self.write(self.plugin, {**manifest, "version": version})
                with self.assertRaisesRegex(checker.CheckError, "identity/version"):
                    checker.plugin_manifests(self.root, {"shell": "0.1.0"}, [])
                with self.assertRaisesRegex(checker.CheckError, "plugin version"):
                    checker.plugin_manifests(self.root, {"shell": version}, [])
                self.write(self.plugin, manifest)

    def test_exact_pin_conflicts_and_manifest_matching(self) -> None:
        """Distinct build metadata and prereleases are exact-pin conflicts."""
        flow = checker.load_yaml(self.flow)
        child = checker.load_yaml(self.child)
        manifest = checker.load_yaml(self.plugin)
        for first, second in (
            ("1.0.0+one", "1.0.0+two"),
            ("1.0.0-rc.1", "1.0.0"),
        ):
            with self.subTest(first=first, second=second):
                self.write(self.flow, {**flow, "plugins": {"shell": first}})
                self.write(self.child, {**child, "plugins": {"shell": second}})
                with self.assertRaisesRegex(checker.CheckError, "conflicting plugin"):
                    checker.inspect_graph(self.flow)
                self.write(self.child, {**child, "plugins": {"shell": first}})
                self.write(self.plugin, {**manifest, "version": second})
                _, pins, actions = checker.inspect_graph(self.flow)
                with self.assertRaisesRegex(checker.CheckError, "identity/version"):
                    checker.plugin_manifests(self.root, pins, actions)
        self.write(self.flow, {**flow, "plugins": {}})
        self.write(self.child, child)
        with self.assertRaisesRegex(checker.CheckError, "matching exact root"):
            checker.inspect_graph(self.flow)

    def test_distinct_plugins_have_independent_pins(self) -> None:
        """Different plugins can use different exact versions in the same graph."""
        flow = checker.load_yaml(self.flow)
        self.write(
            self.flow,
            {**flow, "plugins": {"shell": "0.1.0", "other": "2.3.4+build"}},
        )
        other = self.root / "plugins" / "other" / "plugin.yaml"
        other.parent.mkdir(parents=True)
        other.with_name("schema.json").write_text("{}\n")
        manifest = checker.load_yaml(self.plugin)
        self.write(other, {**manifest, "id": "other", "version": "2.3.4+build"})
        _, pins, actions = checker.inspect_graph(self.flow)
        self.assertEqual(pins, {"shell": "0.1.0", "other": "2.3.4+build"})
        self.assertEqual(
            checker.plugin_manifests(self.root, pins, actions), [other, self.plugin]
        )

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
        """All maintained roots and modules use valid releases and v1 schemas."""
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
                    self.assertIsNotNone(checker.SEMVER.fullmatch(document["version"]))
                    for version in document.get("plugins", {}).values():
                        self.assertIsNotNone(checker.SEMVER.fullmatch(version))


if __name__ == "__main__":
    unittest.main()
