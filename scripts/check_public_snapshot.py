#!/usr/bin/env python3
"""Read-only current-content publication gate; never traverse excluded trees."""

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    "edge_fault_advisory",
    "ai_agent_plugins_canary",
    "cursor_ticket_delivery",
    "hotfix_ticket_delivery",
}
ROOT_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "NOTICE",
    ".gitignore",
    "requirements-dev.txt",
}
DOC_FILES = {
    "docs/compatibility.md",
    "docs/governed-use.md",
    "docs/validation.md",
    "docs/publication.md",
    "docs/history/compatibility-before-publication.md",
    "docs/history/revised-workflow-authoring-step-9.md",
    "docs/history/revised-workflow-authoring-step-10.md",
    "docs/history/revised-workflow-authoring-step-11.md",
    "docs/history/revised-workflow-authoring-step-12.md",
}
SUFFIXES = {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"}
FORBIDDEN = {
    "private",
    "packages",
    "tmp",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "build",
    "runs",
    "signatures",
    "secrets",
    "keys",
}
PATTERNS = {
    "employer identifier": re.compile(rb"su" + rb"mup", re.I),
    "personal identifier": re.compile(
        rb"andr" + rb"ey|andr" + rb"ei|chern" + rb"ykh|@g" + rb"mail\.com", re.I
    ),
    "work identifier": re.compile(
        rb"\bH"
        + rb"B-\d+\b|hardware[._-](?:mcp|backend)|terminal[-_]"
        + rb"hub|fire-"
        + rb"potato|backend_development_plan_"
        + rb"delivery|software_engineer_ticket_"
        + rb"delivery",
        re.I,
    ),
    "absolute home path": re.compile(rb"/(?:Us" + rb"ers|ho" + rb"me)/[^/\s]+", re.I),
    "credential literal": re.compile(
        rb"-----BEGIN (?:[A-Z ]*PRIVATE "
        + rb"KEY)-----|\bAK"
        + rb"IA[A-Z0-9]{16}\b"
        + rb"|\bgh[pousr]_"
        + rb"[A-Za-z0-9]{20,}|github_"
        + rb"pat_[A-Za-z0-9_]{20,}"
        + rb"|\bsk-"
        + rb"[A-Za-z0-9_-]{20,}|Bearer "
        + rb"[A-Za-z0-9._-]{20,}|\bxox"
        + rb"[baprs]-[A-Za-z0-9-]{10,}|https?://[^\s/:]+:[^\s/@]+@",
        re.I,
    ),
    "assigned credential": re.compile(
        rb"(?:api[_-]?key|password|access[_-]?token|client[_-]?secret)"
        rb"[\"']?\s*(?::\s*[\"']?|=\s*[\"'])"
        rb"(?!\$|\{|<|\[|null\b|none\b|example\b|dummy\b|placeholder\b)"
        rb"[A-Za-z0-9_+/.=-]{4,}",
        re.I,
    ),
    "environment credential literal": re.compile(
        rb"(?m)^\s*(?:export\s+)?[A-Z0-9_]*"
        rb"(?:API_KEY|TOKEN|PASSWORD|SECRET)[A-Z0-9_]*\s*=\s*[\"']?"
        rb"(?!\$|\{|<|dummy\b|example\b|placeholder\b|replace\b|your\b)"
        rb"[A-Za-z0-9_+/=-]{8,}(?:[\"']?(?:\s|;|$))"
    ),
}
LINK = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+[^)]*)?\)")
REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*(<[^>]*>|\S+)", re.M)


def candidate_files(root: Path) -> list[PurePosixPath]:
    """Enumerate the index and nonignored working files, without inspecting history."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=True,
            timeout=30,
        )
        names = {p.decode("utf-8") for p in result.stdout.split(b"\0") if p}
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise ValueError("candidate enumeration failed") from None
    return [PurePosixPath(p) for p in sorted(names)]


def path_allowed(relative: PurePosixPath) -> bool:
    """Apply the explicit public allowlist before accessing any candidate bytes."""
    parts = relative.parts
    if (
        not parts
        or relative.is_absolute()
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", p)
            or p in {".", ".."}
            or p.lower() in FORBIDDEN
            or p.lower().startswith("tmp")
            for p in parts
        )
    ):
        return False
    name = parts[-1].lower()
    if any(p.startswith(".") and p not in {".github", ".gitignore"} for p in parts):
        return False
    if (
        re.search(r"(?:^|[._-])inputs?(?:$|[._-])", name)
        and name != "inputs.example.yaml"
    ):
        return False
    if re.search(
        r"(?:^|[._-])(?:keys?|pem|pub|sig|logs?|sqlite|db|p12|pfx|"
        r"credentials?|secrets?|id_rsa|id_ed25519)(?:$|[._-])",
        name,
    ):
        return False
    display = relative.as_posix()
    if display in ROOT_FILES or display in DOC_FILES:
        return True
    if display in {
        ".github/workflows/validate.yml",
        ".github/pull_request_template.md",
    }:
        return True
    return relative.suffix in SUFFIXES and (
        (len(parts) > 1 and parts[0] in {"scripts", "tests"})
        or (len(parts) > 2 and parts[0] == "examples" and parts[1] in EXAMPLES)
    )


def regular_file(root: Path, relative: PurePosixPath) -> bool:
    """Check every component with lstat, refusing symlinks and special files."""
    current = root
    try:
        for index, part in enumerate(relative.parts):
            current = current / part
            mode = current.lstat().st_mode
            if index == len(relative.parts) - 1:
                return stat.S_ISREG(mode)
            if not stat.S_ISDIR(mode):
                return False
    except OSError:
        return False
    return False


def location(relative: PurePosixPath) -> str:
    """Identify safe public paths directly, keeping rejected/sensitive paths opaque."""
    if path_allowed(relative) and not any(
        pattern.search(str(relative).encode()) for pattern in PATTERNS.values()
    ):
        return relative.as_posix()
    return "candidate-" + hashlib.sha256(str(relative).encode()).hexdigest()[:12]


def check_file(
    root: Path, relative: PurePosixPath, candidates: set[PurePosixPath]
) -> list[str]:
    """Check one public text file and its snapshot-contained Markdown links."""
    label = location(relative)
    if not path_allowed(relative):
        return [f"{label}: disallowed public path"]
    if not regular_file(root, relative):
        return [f"{label}: missing, symlinked, or nonregular candidate"]
    try:
        with (root / relative).open("rb") as handle:
            content = handle.read(4 * 1024 * 1024 + 1)
        text = content.decode("utf-8")
    except (OSError, UnicodeError):
        return [f"{label}: unreadable or binary candidate"]
    if len(content) > 4 * 1024 * 1024 or any(
        b < 32 and b not in {9, 10, 13} for b in content
    ):
        return [f"{label}: binary or oversized candidate"]
    errors = []
    for category, pattern in PATTERNS.items():
        match = pattern.search(content) or pattern.search(str(relative).encode())
        if match:
            errors.append(f"{label}: {category}")
    if relative.suffix.lower() != ".md":
        return errors
    for match in list(LINK.finditer(text)) + list(REFERENCE.finditer(text)):
        target = match.group(1).strip("<>")
        try:
            parsed = urlsplit(target)
        except ValueError:
            errors.append(f"{label}: malformed link")
            continue
        if parsed.scheme in {"https", "http", "mailto"} or target.startswith("#"):
            continue
        if parsed.scheme or parsed.netloc:
            errors.append(f"{label}: unsafe local link")
            continue
        decoded = unquote(parsed.path)
        if not decoded:
            continue
        # Normalize lexical '..' without resolving or reading excluded paths.
        joined = os.path.normpath(str(relative.parent / decoded)).replace(os.sep, "/")
        destination = PurePosixPath(joined)
        files = [p for p in candidates if p == destination or destination in p.parents]
        if (
            destination.is_absolute()
            or ".." in destination.parts
            or not files
            or any(not path_allowed(p) or not regular_file(root, p) for p in files)
        ):
            errors.append(f"{label}: broken or nonpublic local link")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Print a reviewed inclusion list only after the whole snapshot passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    try:
        paths = candidate_files(ROOT)
        if not paths:
            raise ValueError("empty candidate snapshot")
        errors = [error for p in paths for error in check_file(ROOT, p, set(paths))]
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.list:
        print("\n".join(p.as_posix() for p in paths))
    else:
        print(f"Snapshot gate passed: {len(paths)} current-content files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
