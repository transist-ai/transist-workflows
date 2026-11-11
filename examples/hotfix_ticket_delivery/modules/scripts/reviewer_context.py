#!/usr/bin/env python3
"""Bounded workflow-specific mirror of runtime decisions in a managed JSONL file.

Only root initialization reads current invocation metadata. Children validate and
update the inherited ledger; their own run.id never replaces its root identity.
The mirror is model context, not authority. Paths are staged data, never a cwd.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

MAX_CONTEXT_BYTES = 65536
MAX_DECISIONS = 128
CONTEXT_SCHEMA = "transist.reviewer_context.v1"
DECISION_SCHEMA = "transist.gate_decision.v1"


class ReviewContextError(ValueError):
    """Reject broken context without replacing it with empty or guessed history."""


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Decode objects without allowing duplicate keys to rewrite evidence."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewContextError("duplicate reviewer-context JSON key")
        result[key] = value
    return result


def _decode(raw: str | bytes) -> Any:
    """Decode bounded UTF-8 JSON with sanitized failures."""
    try:
        return json.loads(raw, object_pairs_hook=_json_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ReviewContextError("invalid reviewer-context JSON") from None


def _encode(value: dict[str, Any]) -> bytes:
    """Encode exact strings in one canonical UTF-8 JSONL record."""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _path(path: Path) -> Path:
    """Require an absolute, nonsymlink staged data path, without workspace guessing."""
    if not path.is_absolute() or ".." in path.parts:
        raise ReviewContextError("absolute staged path required")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ReviewContextError("symlinked context path")
    return path


def _read(path: Path) -> bytes:
    """Read at most the fixed ledger bound from a regular staged file."""
    path = _path(path)
    if not path.is_file():
        raise ReviewContextError("context file missing or nonregular")
    with path.open("rb") as handle:
        raw = handle.read(MAX_CONTEXT_BYTES + 1)
    if len(raw) > MAX_CONTEXT_BYTES:
        raise ReviewContextError("reviewer context exceeds 64 KiB")
    return raw


def _identity_text(value: Any) -> str:
    """Validate an exact nonempty runtime identifier without normalization."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ReviewContextError("invalid reviewer identity")
    return value


def root_identity(metadata: Path) -> str:
    """Read the actual root invocation's typed run.id; never infer a fallback."""
    value = _decode(_read(metadata))
    if not isinstance(value, dict) or not isinstance(value.get("run"), dict):
        raise ReviewContextError("runtime run.id is required")
    return _identity_text(value["run"].get("id"))


def initialize(path: Path, metadata: Path) -> Path:
    """Exclusively create a root ledger from metadata; return its staged path."""
    identity = root_identity(metadata)
    path = _path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_encode({"schema": CONTEXT_SCHEMA, "root_run_id": identity}))
    return path


def _decision(value: Any) -> dict[str, Any]:
    """Validate the exact immutable gate record, retaining actor/reason/timestamp."""
    required = {"schema", "run_id", "gate_id", "step_id", "decision", "decided_at_ms"}
    optional = {"actor", "actor_source", "reason", "review_request"}
    if not isinstance(value, dict) or not required <= value.keys():
        raise ReviewContextError("incomplete reviewer decision")
    if value.keys() - required - optional or value["schema"] != DECISION_SCHEMA:
        raise ReviewContextError("invalid reviewer decision schema")
    for field in ("run_id", "gate_id", "step_id"):
        _identity_text(value[field])
    if value["decision"] not in ("approved", "rejected", "request_changes"):
        raise ReviewContextError("invalid reviewer decision outcome")
    if type(value["decided_at_ms"]) is not int or value["decided_at_ms"] < 0:
        raise ReviewContextError("invalid reviewer timestamp")
    if any(
        key in value and not isinstance(value[key], str)
        for key in optional - {"review_request"}
    ):
        raise ReviewContextError("invalid reviewer text")
    if "review_request" in value:
        request = value["review_request"]
        if (
            not isinstance(request, dict)
            or request.get("schema") != "transist.gate_review_request.v1"
            or any(
                request.get(key) != value[key]
                for key in ("run_id", "gate_id", "step_id")
            )
            or type(request.get("execution")) not in (int, float)
            or not 1 <= request["execution"] <= 2**32 - 1
            or request["execution"] % 1 != 0
            or not isinstance(request.get("review_documents"), list)
        ):
            raise ReviewContextError("invalid decision review scope")
        for revision in request["review_documents"]:
            if (
                not isinstance(revision, dict)
                or revision.get("schema") != "transist.document_revision.v1"
                or not isinstance(revision.get("revision_id"), str)
                or not isinstance(revision.get("blob"), dict)
                or not isinstance(revision["blob"].get("sha256"), str)
            ):
                raise ReviewContextError("invalid reviewed revision")
    return value


def _identity(record: dict[str, Any]) -> tuple[str, str, str, int]:
    """Retain child-run gate scope in the deduplication identity."""
    return tuple(
        record[key] for key in ("run_id", "gate_id", "step_id", "decided_at_ms")
    )


def history(raw: bytes) -> list[dict[str, Any]]:
    """Validate the complete bounded ledger and reject duplicate stored records."""
    if len(raw) > MAX_CONTEXT_BYTES or not raw or not raw.endswith(b"\n"):
        raise ReviewContextError("reviewer context is oversized or incomplete")
    records = [_decode(line) for line in raw.splitlines()]
    header = records[0]
    if not isinstance(header, dict) or set(header) != {"schema", "root_run_id"}:
        raise ReviewContextError("invalid reviewer-context header")
    if header["schema"] != CONTEXT_SCHEMA:
        raise ReviewContextError("invalid reviewer-context schema")
    _identity_text(header["root_run_id"])
    if len(records) - 1 > MAX_DECISIONS:
        raise ReviewContextError("reviewer context exceeds 128 decisions")
    identities = set()
    for record in records[1:]:
        identity = _identity(_decision(record))
        if identity in identities:
            raise ReviewContextError(
                "duplicate or conflicting stored reviewer decision"
            )
        identities.add(identity)
    return records


def capture(path: Path, raw_decision: str | None) -> bool:
    """Append one bound decision to a private update copy, deduplicating re-entry."""
    raw = _read(path)
    records = history(raw)
    if raw_decision is None:
        return False
    if len(raw_decision.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise ReviewContextError("reviewer decision exceeds 64 KiB")
    record = _decision(_decode(raw_decision))
    for previous in records[1:]:
        if _identity(previous) == _identity(record):
            if previous != record:
                raise ReviewContextError(
                    "reviewer decision identity has conflicting content"
                )
            return False
    if len(records) - 1 >= MAX_DECISIONS:
        raise ReviewContextError("reviewer context exceeds 128 decisions")
    updated = raw + _encode(record)
    if len(updated) > MAX_CONTEXT_BYTES:
        raise ReviewContextError("reviewer context exceeds 64 KiB")
    # Runtime owns cross-invocation serialization and atomic document publication.
    # This private copy is discarded if the command or invocation fails.
    path.write_bytes(updated)
    return True


def main() -> int:
    """Initialize at the root or update inherited context from bound gate data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("init", "capture"))
    parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "init":
            metadata = os.environ.get("TRANSIST_RUNTIME_METADATA_FILE")
            if not metadata:
                raise ReviewContextError("runtime metadata file required")
            initialize(args.file, Path(metadata))
        else:
            capture(args.file, os.environ.get("TRANSIST_GATE_DECISION_JSON"))
        return 0
    except (OSError, ValueError, UnicodeError):
        print("Reviewer context invalid; no history published", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
