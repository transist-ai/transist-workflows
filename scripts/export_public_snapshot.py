#!/usr/bin/env python3
"""Export approved current contents/modes, never development history or a commit."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from check_public_snapshot import ROOT, candidate_files, check_file
from source_identity import inventory, read_regular, source_identity


def approved_files(root: Path) -> list[Path]:
    """Fail closed on every candidate before any export destination is created."""
    paths = candidate_files(root)
    if not paths:
        raise ValueError("empty publication inventory")
    errors = [error for p in paths for error in check_file(root, p, set(paths))]
    if errors:
        raise ValueError("\n".join(errors))
    return [Path(p) for p in paths]


def stage_verified(destination: Path, expected: dict[Path, tuple[bytes, int]]) -> None:
    """Initialize template-free main and verify every staged blob/mode in isolation."""
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    with tempfile.TemporaryDirectory(prefix="workflow-export-git-") as home:
        environment.update(
            HOME=home,
            XDG_CONFIG_HOME=home,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_ATTR_NOSYSTEM="1",
        )

        def git(*arguments: str) -> bytes:
            """Run Git without global config, attributes, hooks or inherited filters."""
            return subprocess.run(
                [
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "core.filemode=true",
                    "-c",
                    "core.attributesFile=" + os.devnull,
                    *arguments,
                ],
                cwd=destination,
                env=environment,
                check=True,
                capture_output=True,
                timeout=30,
            ).stdout

        git("init", "--quiet", "--initial-branch=main", "--template=", ".")
        git("add", "--", ".")
        seen = set()
        for entry in git("ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            header, name = entry.split(b"\t", 1)
            mode, digest, stage = header.split()
            path = Path(name.decode())
            if path not in expected or stage != b"0" or path in seen:
                raise ValueError("unexpected indexed path/stage")
            content, permissions = expected[path]
            expected_mode = b"100755" if permissions & 0o111 else b"100644"
            if (
                mode != expected_mode
                or git("cat-file", "blob", digest.decode()) != content
            ):
                raise ValueError("indexed bytes/modes differ")
            seen.add(path)
        if seen != set(expected):
            raise ValueError("indexed inventory differs")
        if git("for-each-ref") or git("remote"):
            raise ValueError("fresh repository unexpectedly contains refs/remotes")


def export_snapshot(root: Path, destination: Path, init_git: bool = False) -> Path:
    """Copy/revalidate frozen source and write an external receipt only on success."""
    root = root.resolve(strict=True)
    destination = destination.absolute()
    resolved = destination.resolve()
    receipt = destination.with_name(destination.name + ".inventory.json")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must not exist")
    if receipt.exists() or receipt.is_symlink():
        raise ValueError("external receipt must not exist")
    if resolved.is_relative_to(root) or root.is_relative_to(resolved):
        raise ValueError("destination must be outside source")
    if not destination.parent.is_dir() or destination.parent != resolved.parent:
        raise ValueError("destination parent must exist and be canonical")
    paths = approved_files(root)
    expected = {p: read_regular(root, p) for p in paths}
    provenance = source_identity(root)
    if provenance["files"] != inventory(expected)["files"]:
        raise ValueError("source changed before export")
    destination.mkdir(mode=0o700)
    for relative, (content, mode) in expected.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(mode)
    errors = [error for p in paths for error in check_file(destination, p, set(paths))]
    if errors:
        raise ValueError("copied publication content rejected: " + "; ".join(errors))
    if init_git:
        stage_verified(destination, expected)
    if approved_files(root) != paths:
        raise ValueError("source inventory changed during export")
    for relative, frozen in expected.items():
        if read_regular(root, relative) != frozen:
            raise ValueError("source changed during export")
        if read_regular(destination, relative) != frozen:
            raise ValueError("copied bytes/modes differ")
    report = {**inventory(expected), "source": provenance, "git_initialized": init_git}
    with receipt.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return receipt


def main() -> int:
    """Export into an absent external destination without committing or publishing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--init-git", action="store_true")
    args = parser.parse_args()
    try:
        receipt = export_snapshot(ROOT, args.destination, args.init_git)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Export failed; no approved receipt: {error}\n")
    print(f"Export verified; external inventory: {receipt}; no commit created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
