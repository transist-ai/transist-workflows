#!/usr/bin/env python3
"""Validate public example graphs with Transist 0.1.1; never dispatch a workflow.

Only source-mode `workflows check --path` is used. Installed-workflow readiness
can probe adapters and is deliberately excluded. No environment credentials are
inherited; static success is not live readiness, signing, or integration evidence.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

from check_public_snapshot import EXAMPLES, regular_file

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1"
CATALOG_VERSION = "0.1.0"
SEMVER = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
)
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
DEFERRED_CODES = {
    "mutable_variable",
    "step_output",
    "input_schema",
    "deferred_to_dispatch",
}
OLLAMA_SOURCES = (
    "main.go",
    "execute.go",
    "lifecycle.go",
    "lean_io.go",
    "native_darwin.go",
    "native_linux.go",
    "native_unsupported.go",
)


class CheckError(ValueError):
    """A sanitized validation failure suitable for console output."""


class UniqueLoader(yaml.SafeLoader):
    """Safe YAML loader that refuses duplicate mapping keys."""


def unique_mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict:
    """Construct a mapping without silently overwriting pins or metadata."""
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, (str, int, float, bool)) or key in result:
            raise CheckError("duplicate or invalid YAML mapping key")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping, suppressing source bytes from parser diagnostics."""
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    except CheckError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError):
        raise CheckError("unreadable or invalid YAML document") from None
    if not isinstance(data, dict):
        raise CheckError("YAML document must be a mapping")
    return data


def contained_file(base: Path, value: str) -> Path:
    """Resolve a literal asset under its declaring directory, without symlinks."""
    if not isinstance(value, str) or not value or "{{" in value:
        raise CheckError("asset path must be a literal")
    if any(ord(character) < 32 for character in value):
        raise CheckError("asset path contains unsafe control characters")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in value:
        raise CheckError("asset path escapes its declaring directory")
    if not regular_file(base, relative):
        raise CheckError("missing, symlinked, or nonregular asset")
    return base / relative


def walk(value: Any) -> list[dict[str, Any]]:
    """Collect nested mappings for static asset and action checks."""
    if isinstance(value, dict):
        return [value] + [node for child in value.values() for node in walk(child)]
    if isinstance(value, list):
        return [node for child in value for node in walk(child)]
    return []


def strings(value: Any) -> list[str]:
    """Collect nested string values to check source asset references."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for child in value.values() for s in strings(child)]
    if isinstance(value, list):
        return [s for child in value for s in strings(child)]
    return []


def check_control_expressions(steps: Any) -> None:
    """Reject word-form logical operators in controls without exposing source text.

    Inspect nested step mappings, ignoring quoted values and dotted references.
    This is a narrow authoring guard, not a replacement for runtime validation.
    """
    for node in walk(steps):
        for block_name, fields in (("if", ("guard",)), ("loop", ("until", "while"))):
            block = node.get(block_name)
            if not isinstance(block, dict):
                continue
            for field in fields:
                expression = block.get(field)
                if not isinstance(expression, str):
                    continue
                unquoted = re.sub(
                    r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", "", expression
                )
                if re.search(r"(?<![\w.])(?:and|or)(?![\w.])", unquoted, re.IGNORECASE):
                    raise CheckError(
                        "unsupported logical operator in control expression; "
                        "use && or || instead of word-form operators"
                    )


def check_control_sequences(steps: list[dict[str, Any]]) -> None:
    """Reject ref-based loop/if bodies that do not match adjacent physical steps.

    This catches misplaced/reused guards before installing dependencies or calling
    runtime validation. Inline control bodies remain the runtime's responsibility.
    """
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        for block_name, field in (("loop", "body"), ("if", "then")):
            block = step.get(block_name)
            if not isinstance(block, dict):
                continue
            references = block.get(field)
            if not isinstance(references, list) or not references:
                continue
            if not all(isinstance(ref, dict) and "ref" in ref for ref in references):
                continue
            first = index + 1
            last = first + len(references)
            following = steps[first:last]
            expected = [
                node.get("id") if isinstance(node, dict) else None for node in following
            ]
            if [ref["ref"] for ref in references] != expected:
                raise CheckError(
                    "control references must follow contiguous physical step order"
                )


def inspect_graph(workflow: Path) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    """Check all declared modules, pins, IDs, detached assets, and invoke references."""
    root = load_yaml(workflow)
    pins: dict[str, str] = {}
    identities: set[str] = set()
    visiting: set[Path] = set()
    visited: set[Path] = set()
    actions: list[str] = []

    def visit(path: Path, is_root: bool) -> None:
        """Validate a declared document, rejecting cycles and conflicting metadata."""
        if path in visiting:
            raise CheckError("module graph contains a cycle")
        if path in visited:
            return
        visiting.add(path)
        doc = root if is_root else load_yaml(path)
        expected = "transist.flow.v1" if is_root else "transist.module.v1"
        identity = doc.get("id")
        if (
            doc.get("schema") != expected
            or not isinstance(identity, str)
            or not IDENTIFIER.fullmatch(identity)
        ):
            raise CheckError("invalid workflow/module schema or identity")
        if identity in identities:
            raise CheckError("duplicate workflow/module identity")
        identities.add(identity)
        if not isinstance(doc.get("version"), str) or not doc["version"]:
            raise CheckError("missing workflow/module version")
        if doc["version"] != CATALOG_VERSION:
            kind = "workflow" if is_root else "module"
            raise CheckError(f"{kind} version must be {CATALOG_VERSION}")
        if not isinstance(doc.get("steps"), list):
            raise CheckError("workflow/module steps must be a list")
        if not isinstance(doc.get("inputs", {}), dict):
            raise CheckError("workflow/module inputs must be a mapping")
        declared = doc.get("plugins", {})
        if not isinstance(declared, dict):
            raise CheckError("plugin pins must be a mapping")
        for plugin, version in declared.items():
            if (
                not isinstance(plugin, str)
                or not IDENTIFIER.fullmatch(plugin)
                or not isinstance(version, str)
                or version != CATALOG_VERSION
            ):
                raise CheckError(
                    f"plugin pins require safe IDs and version {CATALOG_VERSION}"
                )
            if plugin in pins and pins[plugin] != version:
                raise CheckError("conflicting plugin version pins")
            pins[plugin] = version
        step_ids = set()
        if not isinstance(doc.get("cleanup", []), list):
            raise CheckError("workflow/module cleanup must be a list")
        check_control_expressions([doc["steps"], doc.get("cleanup", [])])
        check_control_sequences(doc["steps"])
        check_control_sequences(doc.get("cleanup", []))
        for node in walk([doc["steps"], doc.get("cleanup", [])]):
            if "id" in node and (
                "uses" in node
                or "control" in node
                or "steps" in node
                or "module" in node
            ):
                if (
                    not isinstance(node["id"], str)
                    or not IDENTIFIER.fullmatch(node["id"])
                    or node["id"] in step_ids
                ):
                    raise CheckError("invalid or duplicate step ID")
                step_ids.add(node["id"])
            if "uses" in node:
                uses = node["uses"]
                if not isinstance(uses, str) or not re.fullmatch(
                    r"(?:process|http|mcp):[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", uses
                ):
                    raise CheckError("invalid action reference")
                actions.append(uses)
        for node in walk(doc):
            if "prompt_file" in node:
                contained_file(path.parent, node["prompt_file"])
            if "skills" in node:
                if not isinstance(node["skills"], list):
                    raise CheckError("skills must be a list of contained assets")
                for asset in node["skills"]:
                    contained_file(path.parent, asset)
        for value in strings(doc):
            for asset in re.findall(r"source://([^\s\"'<>]+)", value):
                contained_file(path.parent, asset)
        modules = doc.get("modules", {})
        if not isinstance(modules, dict):
            raise CheckError("module declarations must be a mapping")
        for declaration in modules.values():
            if not isinstance(declaration, dict) or "path" not in declaration:
                raise CheckError("module declaration requires a path")
            visit(contained_file(path.parent, declaration["path"]), False)
        visiting.remove(path)
        visited.add(path)

    visit(workflow, True)
    if any(
        root.get("plugins", {}).get(plugin) != version
        for plugin, version in pins.items()
    ):
        raise CheckError("every module pin requires a matching exact root plugin pin")
    for uses in actions:
        plugin = uses.split(":", 1)[1].split("/", 1)[0]
        if plugin not in pins or root.get("plugins", {}).get(plugin) != pins[plugin]:
            raise CheckError("every action requires an exact root plugin pin")
    return root, pins, sorted(set(actions))


def selected_payload(manifest_path: Path, manifest: dict[str, Any]) -> list[str]:
    """Require selected payloads; always rebuild Ollama from reviewed source."""
    package = manifest.get("package")
    files = package.get("files") if isinstance(package, dict) else None
    if not isinstance(files, list) or not files:
        raise CheckError("plugin package.files must select a nonempty real payload")
    selected: list[str] = []
    for value in files:
        if not isinstance(value, str) or not value or "\\" in value:
            raise CheckError("invalid selected package file")
        if any(ord(character) < 32 for character in value):
            raise CheckError("selected package file has unsafe control characters")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or "{{" in value:
            raise CheckError("selected package file escapes package")
        name = relative.as_posix()
        if name in selected or name == "plugin.yaml":
            raise CheckError("duplicate or implicit selected package file")
        selected.append(name)
        entrypoint = manifest.get("entrypoint")
        buildable = (
            manifest.get("id") == "ollama.cli"
            and name == "bin/ollama.cli"
            and isinstance(entrypoint, dict)
            and entrypoint.get("command") == name
        )
        if not buildable:
            if not regular_file(manifest_path.parent, relative):
                raise CheckError("selected plugin payload missing or nonregular")
            continue
        # Missing build output is allowed; symlink/special ancestors are not.
        current = manifest_path.parent
        for part in relative.parts:
            current /= part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                break
            if current == manifest_path.parent / relative and stat.S_ISREG(mode):
                break
            if not stat.S_ISDIR(mode):
                raise CheckError("Ollama build output has an unsafe source component")
        else:
            raise CheckError("Ollama build output is not a regular selected file")
        contained_file(manifest_path.parent, "go.mod")
        for filename in OLLAMA_SOURCES:
            contained_file(manifest_path.parent, f"cmd/plugin/{filename}")
    return selected


def check_schema_graph(
    package: Path, schema: Path, selected: set[str], visited: set[Path]
) -> None:
    """Check transitive local schema references within the selected payload."""
    if schema in visited:
        return
    visited.add(schema)
    if schema.relative_to(package).as_posix() not in selected:
        raise CheckError("action schema/reference is not selected in package.files")
    try:
        document = json.loads(schema.read_text(encoding="utf-8"))
        if not isinstance(document, (dict, bool)):
            raise ValueError
    except (OSError, UnicodeError, ValueError):
        raise CheckError("invalid plugin action schema document") from None
    for node in walk(document):
        for keyword in ("$ref", "$dynamicRef", "$recursiveRef"):
            if keyword not in node:
                continue
            value = node[keyword]
            if not isinstance(value, str):
                raise CheckError("invalid schema reference")
            try:
                parsed = urlsplit(value)
            except ValueError:
                raise CheckError("invalid schema reference") from None
            decoded = unquote(parsed.path)
            if parsed.scheme or parsed.netloc or parsed.query or "\\" in decoded:
                raise CheckError(
                    "nonlocal schema reference refused for offline validation"
                )
            if not decoded:
                continue
            if Path(decoded).is_absolute():
                raise CheckError("schema reference escapes selected package")
            base = schema.parent.relative_to(package)
            relative = Path(os.path.normpath(str(base / decoded)))
            target = contained_file(package, relative.as_posix())
            check_schema_graph(package, target, selected, visited)


def plugin_manifests(
    checkout: Path, pins: dict[str, str], actions: list[str]
) -> list[Path]:
    """Select only exact public plugin packages and check their action metadata."""
    manifests = []
    for plugin, version in sorted(pins.items()):
        if version != CATALOG_VERSION:
            raise CheckError(f"plugin version must be {CATALOG_VERSION}")
        path = contained_file(checkout, f"plugins/{plugin}/plugin.yaml")
        manifest = load_yaml(path)
        if (
            manifest.get("schema") != "transist.plugin.v1"
            or manifest.get("id") != plugin
            or manifest.get("version") != version
        ):
            raise CheckError(
                "plugin manifest identity/version does not match exact pin"
            )
        selected = set(selected_payload(path, manifest))
        visited: set[Path] = set()
        declared = manifest.get("actions")
        if not isinstance(declared, list):
            raise CheckError("plugin actions must be a list")
        names = set()
        for action in declared:
            if (
                not isinstance(action, dict)
                or not isinstance(action.get("name"), str)
                or action["name"] in names
            ):
                raise CheckError("invalid or duplicate plugin action ID")
            names.add(action["name"])
            for field in ("input_schema", "output_schema"):
                schema = contained_file(path.parent, action.get(field))
                check_schema_graph(path.parent, schema, selected, visited)
        for uses in actions:
            adapter, reference = uses.split(":", 1)
            action_plugin, action_name = reference.split("/", 1)
            if action_plugin == plugin and (
                adapter != manifest.get("adapter") or action_name not in names
            ):
                raise CheckError("action or adapter is absent from pinned plugin")
        manifests.append(path)
    return manifests


def isolated_environment(base: Path) -> dict[str, str]:
    """Build an environment with disposable user/config/temp directories."""
    user = base / "user"
    user.mkdir()
    (user / ".cursor").mkdir()
    temp = base / "temp"
    temp.mkdir()
    return {
        # Retain only PATH for static prerequisite discovery, never credentials.
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(user),
        "USERPROFILE": str(user),
        "XDG_CONFIG_HOME": str(user / "config"),
        "XDG_CACHE_HOME": str(user / "cache"),
        "XDG_DATA_HOME": str(user / "data"),
        "TMPDIR": str(temp),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
    }


def build_ollama(
    source: Path, destination: Path, scratch: Path, env: dict[str, str]
) -> None:
    """Build bin/ollama.cli from the complete reviewed stdlib-only source inventory."""
    go = shutil.which("go", path=env["PATH"])
    if not go or not Path(go).is_absolute():
        raise CheckError("Ollama adapter build requires an absolute Go executable")
    module = contained_file(source, "go.mod")
    # This one documented build recipe has no third-party module dependencies.
    try:
        lines = [
            line.strip()
            for line in module.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError):
        raise CheckError("unreadable Ollama module build recipe") from None
    if (
        len(lines) != 2
        or lines[0] != "module ollama.cli"
        or not re.fullmatch(r"go \d+\.\d+(?:\.\d+)?", lines[1])
    ):
        raise CheckError("Ollama build requires the documented stdlib-only go.mod")
    build = scratch / "ollama-build"
    actual = {
        path.name
        for path in (source / "cmd/plugin").glob("*.go")
        if not path.name.endswith("_test.go")
    }
    if actual != set(OLLAMA_SOURCES):
        raise CheckError("Ollama source inventory changed; review the build recipe")
    build.mkdir()
    (build / "cmd" / "plugin").mkdir(parents=True)
    shutil.copyfile(module, build / "go.mod")
    for filename in OLLAMA_SOURCES:
        shutil.copyfile(
            contained_file(source, f"cmd/plugin/{filename}"),
            build / "cmd" / "plugin" / filename,
        )
    build_env = dict(env)
    for key in ("GOCACHE", "GOTMPDIR", "GOPATH"):
        directory = scratch / key.lower()
        directory.mkdir()
        build_env[key] = str(directory)
    build_env.update(
        {
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "GOENV": "off",
            "CGO_ENABLED": "1" if sys.platform == "darwin" else "0",
            "GO111MODULE": "on",
        }
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                go,
                "build",
                "-mod=readonly",
                "-trimpath",
                "-buildvcs=false",
                "-o",
                str(destination),
                "./cmd/plugin",
            ],
            cwd=build,
            env=build_env,
            capture_output=True,
            timeout=240,
        )
    except (OSError, subprocess.SubprocessError):
        raise CheckError(
            "offline Ollama adapter build unavailable or timed out"
        ) from None
    (scratch / "ollama-build.stdout").write_bytes(result.stdout)
    (scratch / "ollama-build.stderr").write_bytes(result.stderr)
    if result.returncode or not regular_file(
        destination.parent, Path(destination.name)
    ):
        raise CheckError("offline Ollama adapter build failed; no substitute payload")
    if destination.stat().st_size == 0 or not os.access(destination, os.X_OK):
        raise CheckError("offline Ollama build did not produce an executable payload")
    if sys.platform == "darwin":
        # Go 1.22 + current Apple external linker can leave an invalid Mach-O
        # ad-hoc signature. Seal only this freshly built scratch executable.
        # This uses no key/identity and is unrelated to Transist package trust.
        try:
            for arguments in (
                ["--force", "--sign", "-", str(destination)],
                ["--verify", str(destination)],
            ):
                signed = subprocess.run(
                    ["/usr/bin/codesign", *arguments],
                    env=build_env,
                    capture_output=True,
                    timeout=30,
                )
                if signed.returncode:
                    raise CheckError("scratch Ollama Mach-O ad-hoc sealing failed")
        except (OSError, subprocess.SubprocessError):
            raise CheckError("scratch Ollama Mach-O sealing unavailable") from None
    version = subprocess.run(
        [go, "version"], env=build_env, capture_output=True, text=True, timeout=15
    )
    if version.returncode:
        raise CheckError("Ollama toolchain identity unavailable")
    (scratch / "ollama-build-receipt.json").write_text(
        json.dumps(
            {
                "go": go,
                "version": version.stdout.strip(),
                "cgo": build_env["CGO_ENABLED"],
                "command": [
                    go,
                    "build",
                    "-mod=readonly",
                    "-trimpath",
                    "-buildvcs=false",
                    "-o",
                    str(destination),
                    "./cmd/plugin",
                ],
                "darwin_adhoc_sealed": sys.platform == "darwin",
                "sources": {
                    name.relative_to(build)
                    .as_posix(): hashlib.sha256(name.read_bytes())
                    .hexdigest()
                    for name in sorted(build.rglob("*"))
                    if name.is_file()
                },
                "binary_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            },
            indent=2,
        )
    )


def stage_plugin(manifest_path: Path, scratch: Path, env: dict[str, str]) -> Path:
    """Stage selected bytes; build Ollama explicitly, ignoring stale local outputs."""
    manifest = load_yaml(manifest_path)
    selected = selected_payload(manifest_path, manifest)
    identity = manifest.get("id")
    if not isinstance(identity, str) or not IDENTIFIER.fullmatch(identity):
        raise CheckError("invalid staging plugin identity")
    package = scratch / "dependencies" / identity
    package.mkdir(parents=True)
    shutil.copyfile(manifest_path, package / "plugin.yaml")
    for name in selected:
        destination = package / name
        if identity == "ollama.cli" and name == "bin/ollama.cli":
            build_ollama(manifest_path.parent, destination, scratch, env)
        elif regular_file(manifest_path.parent, Path(name)):
            source = contained_file(manifest_path.parent, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        else:
            raise CheckError("selected payload disappeared before staging")
    return package / "plugin.yaml"


def configure_static_home(home: Path) -> None:
    """Enable process-delivery metadata only in the disposable standalone home."""
    path = home / "config.yaml"
    config = load_yaml(path)
    if config.get("runtime", {}).get("mode") != "standalone":
        raise CheckError("disposable home did not initialize in standalone mode")
    policy = config.setdefault("policy", {})
    delivery = policy.setdefault("remote_secret_delivery", {})
    delivery["process"] = True
    path.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")


def runtime_command(
    binary: Path, args: list[str], cwd: Path, env: dict[str, str], phase: str
) -> dict[str, Any]:
    """Run an allowlisted static command, suppressing raw subprocess output."""
    allowed = (
        args[:2] == ["home", "init"]
        or args[:2] == ["plugins", "install"]
        or (
            args[:2] == ["workflows", "check"]
            and "--path" in args
            and "--workflow" not in args
        )
    )
    if not allowed:
        raise CheckError("nonstatic runtime command refused")
    try:
        result = subprocess.run(
            [str(binary), *args, "--format", "json", "--ui", "plain"],
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        raise CheckError(
            f"{phase}: runtime unavailable or timed out; incomplete"
        ) from None
    # 0.1.0 home initialization emits plain text even with --format json.
    if (
        args[:2] == ["home", "init"]
        and result.returncode == 0
        and result.stdout.startswith(b"initialized ")
    ):
        return {"status": "initialized"}
    try:
        report = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise CheckError(
            f"{phase}: runtime returned invalid JSON; incomplete"
        ) from None
    if not isinstance(report, dict):
        raise CheckError(f"{phase}: invalid runtime report; incomplete")
    nodes = walk(report)
    if result.returncode or any(
        n.get("status") in ("failed", "blocked", "error") or n.get("valid") is False
        for n in nodes
    ):
        codes = sorted(
            {
                n.get("code", n.get("kind", ""))
                for n in nodes
                if n.get("status") in ("failed", "blocked", "error")
                and isinstance(n.get("code", n.get("kind", "")), str)
            }
        )
        # Never emit source text, paths, secret names, or runtime messages.
        category = (
            "missing runtime secrets"
            if any("secret" in c for c in codes)
            else "runtime validation failure"
        )
        known_codes = {
            "request_preparation",
            "step_policy",
            "adapter_preflight",
            "run_policy",
            "workflow_prerequisite",
            "approval_policy",
            "bound_validation",
            "authored_definition",
            "required_input",
            "secret_resolution",
            "action_schema",
            "action_input_schema",
            "plugin_missing",
            "secret_delivery_denied",
            "input_schema",
            "input_missing",
            "capability_not_granted",
            "plugin_contract",
            "filesystem_workspace_boundary",
            "network_egress_boundary",
            "plugin_prerequisite",
        }
        safe_codes = sorted(known_codes.intersection(codes))
        if safe_codes:
            category += " [" + ", ".join(safe_codes) + "]"
        if any(
            isinstance(n.get("message"), str)
            and "overlaps protected runtime root" in n["message"]
            and n.get("status") == "failed"
            for n in nodes
        ):
            category += " (scratch user grant overlaps a protected runtime root)"
            if sys.platform == "darwin":
                category += "; use --home-base <repository>/tmp on macOS"
        raise CheckError(f"{phase}: {category}; incomplete (exit {result.returncode})")
    if args[:2] == ["workflows", "check"]:
        checks = [n["checks"] for n in nodes if "checks" in n]
        if not checks or any(not isinstance(c, list) or not c for c in checks):
            raise CheckError(f"{phase}: missing validation checks; incomplete")
        statuses = ("passed", "warning", "not_evaluated", "deferred_to_dispatch")
        if any(
            not isinstance(check, dict) or check.get("status") not in statuses
            for group in checks
            for check in group
        ):
            raise CheckError(f"{phase}: unknown validation status; incomplete")
        if phase == "bound source" and any(
            check["status"] != "passed"
            and not (
                check["status"] == "not_evaluated"
                and check.get("code") in {"secret_value", "external_state"}
            )
            and not (
                check["status"] == "deferred_to_dispatch"
                and check.get("code") in DEFERRED_CODES
            )
            for group in checks
            for check in group
        ):
            raise CheckError(
                "bound source: static binding or authority evidence is incomplete; "
                "only declared payload dependencies/probes may defer to dispatch; "
                "live secret values and external state are not evaluated"
            )
    return report


def representative_inputs(
    example: Path, scratch: Path, definition: dict[str, Any]
) -> Path:
    """Bind the sample to a fictional workspace without altering source."""
    sample = contained_file(example, "inputs.example.yaml")
    inputs = load_yaml(sample)
    workspace = scratch / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Synthetic validation workspace\n")
    (workspace / "diagnostics.txt").write_text(
        "Fictional diagnostic fixture; no device data.\n"
    )
    (workspace / ".github").mkdir()
    (workspace / ".github" / "pull_request_template.md").write_text("## Summary\n")
    for key in ("repo_path", "workspace_path"):
        if key in definition.get("inputs", {}):
            inputs[key] = str(workspace)
    # Include defaults through the genuine compiler; never fabricate secret values.
    target = scratch / "inputs.json"
    target.write_text(json.dumps(inputs, sort_keys=True), encoding="utf-8")
    return target


def validate_example(
    example: Path, binary: Path, checkout: Path, home_base: Path
) -> None:
    """Install exact plugins and check unbound/bound source in a fresh home."""
    workflow = contained_file(example, "workflow.yaml")
    definition, pins, actions = inspect_graph(workflow)
    if definition["id"] != example.name:
        raise CheckError("root workflow identity must match example directory")
    manifests = plugin_manifests(checkout, pins, actions)
    with tempfile.TemporaryDirectory(
        prefix="transist-example-", dir=home_base
    ) as directory:
        scratch = Path(directory)
        env = isolated_environment(scratch)
        home = scratch / "home"
        runtime_command(
            binary,
            ["home", "init", "--home", str(home), "--mode", "standalone"],
            scratch,
            env,
            "home init",
        )
        configure_static_home(home)
        for manifest in manifests:
            staged = stage_plugin(manifest, scratch, env)
            runtime_command(
                binary,
                ["plugins", "install", "--path", str(staged), "--home", str(home)],
                scratch,
                env,
                "plugin install",
            )
        runtime_command(
            binary,
            ["workflows", "check", "--path", str(workflow), "--home", str(home)],
            scratch,
            env,
            "unbound source",
        )
        inputs = representative_inputs(example, scratch, definition)
        runtime_command(
            binary,
            [
                "workflows",
                "check",
                "--path",
                str(workflow),
                "--inputs-file",
                str(inputs),
                "--home",
                str(home),
            ],
            scratch,
            env,
            "bound source",
        )
        if (home / "runs").exists() and any((home / "runs").iterdir()):
            raise CheckError("static validation unexpectedly created run state")


def approved_home_base(value: str) -> Path:
    """Accept system temp or explicit nonsymlink repository/sibling tmp storage."""
    base = Path(value)
    roots = (ROOT / "tmp", ROOT.parent / "tmp")
    if base.is_absolute() and any(base.is_relative_to(root) for root in roots):
        if ".." in base.parts:
            raise CheckError("repository tmp path contains unsafe components")
        current = Path(base.anchor)
        try:
            for component in base.parts[1:]:
                current /= component
                if not stat.S_ISDIR(current.lstat().st_mode):
                    raise CheckError(
                        "repository tmp must have nonsymlink directory components"
                    )
        except OSError:
            raise CheckError(
                "repository tmp must be an existing regular directory"
            ) from None
        return base.resolve()
    if (
        not base.is_absolute()
        or not base.is_dir()
        or not base.resolve().is_relative_to(Path("/tmp").resolve())
    ):
        raise CheckError(
            "--home-base requires existing /tmp, repository tmp or sibling tmp storage"
        )
    return base.resolve()


def check_version(binary: Path) -> None:
    """Require an explicit executable reporting precisely the target version."""
    if (
        not binary.is_absolute()
        or not binary.is_file()
        or not os.access(binary, os.X_OK)
    ):
        raise CheckError("--transist must be an absolute executable path")
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            timeout=15,
            env={"PATH": os.defpath, "NO_COLOR": "1"},
        )
    except (OSError, subprocess.SubprocessError):
        raise CheckError("runtime version probe failed") from None
    if result.returncode or result.stdout.strip() != f"transist {VERSION}".encode():
        raise CheckError(
            f"runtime must report transist {VERSION}; compatibility check incomplete"
        )


def main(argv: list[str] | None = None) -> int:
    """Validate four public examples and report sanitized static outcomes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", required=True, type=Path)
    parser.add_argument("--plugins-dir", required=True, type=Path)
    parser.add_argument("--home-base", default="/tmp")
    parser.add_argument("--example", action="append", choices=sorted(EXAMPLES))
    args = parser.parse_args(argv)
    selected = set(args.example) if args.example else EXAMPLES
    try:
        home_base = approved_home_base(args.home_base)
        check_version(args.transist)
        if not args.plugins_dir.is_absolute() or not args.plugins_dir.is_dir():
            raise CheckError(
                "--plugins-dir must be an absolute public checkout directory"
            )
        examples = ROOT / "examples"
        if examples.is_symlink() or not examples.is_dir():
            raise CheckError("missing or symlinked examples root")
        children = {p.name for p in examples.iterdir()}
        if children - EXAMPLES:
            raise CheckError("unexpected example directories; incomplete")
    except (CheckError, OSError, RuntimeError) as error:
        message = (
            str(error)
            if isinstance(error, CheckError)
            else "configuration access failed"
        )
        print(f"Examples incomplete: {message}", file=sys.stderr)
        return 1
    failed = False
    for name in sorted(selected):
        try:
            if (examples / name).is_symlink():
                raise CheckError("symlinked example directory")
            validate_example(
                examples / name, args.transist, args.plugins_dir, home_base
            )
            print(
                f"{name}: static source checks passed "
                "(unbound and representative bound)"
            )
        except (CheckError, OSError, RecursionError, TypeError) as error:
            # Arbitrary I/O errors may contain sensitive paths.
            message = (
                str(error) if isinstance(error, CheckError) else "file operation failed"
            )
            print(f"{name}: incomplete: {message}", file=sys.stderr)
            failed = True
    if not failed:
        print(
            "Static example validation complete; "
            "live prerequisites and secrets not evaluated."
        )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
