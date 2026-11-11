#!/usr/bin/env python3
"""Automatic static-only gate: parse source and run static analysis, never helpers."""

import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from check_examples import inspect_graph, load_yaml
from check_public_snapshot import EXAMPLES, candidate_files, check_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "diagnostic_advisory",
    "approved_draft_publication",
    "two_approval_revision",
}


def inspect_source(root: Path, paths: list[Path]) -> None:
    """Parse approved files and all seven graphs without importing their helpers."""
    for relative in paths:
        path = root / relative
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        elif path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix in {".yaml", ".yml"}:
            load_yaml(path)
    for directory, expected in (
        (root / "examples", EXAMPLES),
        (root / "tests/fixtures/conversational_authoring", FIXTURES),
    ):
        actual = {p.name for p in directory.iterdir() if p.is_dir()}
        if actual != expected:
            raise ValueError("maintained graph inventory drift")
        for name in sorted(expected):
            workflow = directory / name / "workflow.yaml"
            if workflow.relative_to(root) not in paths:
                raise ValueError("maintained graph absent from approved inventory")
            inspect_graph(workflow)


def commands(paths: list[Path], staging: Path) -> list[list[str]]:
    """Return the finite static-tool commands; never execute an authored program."""
    python = [str(p) for p in paths if p.suffix == ".py"]
    shell = [str(p) for p in paths if p.suffix == ".sh"]
    return [
        [sys.executable, "-m", "black", "--check", *python],
        [sys.executable, "-m", "flake8", "--max-line-length=88", *python],
        *([["shellcheck", *shell]] if shell else []),
        ["actionlint", ".github/workflows/validate.yml"],
        ["gitleaks", "dir", "--redact", "--no-banner", str(staging)],
    ]


def main() -> int:
    """Validate current approved bytes, then scan only their disposable copy."""
    try:
        paths = candidate_files(ROOT)
        if not paths:
            raise ValueError("empty public inventory")
        errors = [error for p in paths for error in check_file(ROOT, p, set(paths))]
        if errors:
            raise ValueError("\n".join(errors))
        paths = [Path(p) for p in paths]
        inspect_source(ROOT, paths)
        with tempfile.TemporaryDirectory(prefix="workflow-static-") as directory:
            staging = Path(directory)
            for relative in paths:
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            for command in commands(paths, staging):
                subprocess.run(command, cwd=ROOT, check=True, timeout=180)
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        print(f"Static checks failed: {error}", file=sys.stderr)
        return 1
    print(f"Static checks passed: {len(paths)} approved files; no runtime execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
