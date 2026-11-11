#!/usr/bin/env python3
"""Exercise the selected actual peer helper after a temporary same-path source swap.

This is an explicit native integration check, separate from offline unit discovery.
It uses a real isolated runtime home and CLI, but creates no workflow run and makes
no provider call. Only an owned temporary helper copy is changed, never its source
checkout. The full installed workflow matrix remains a separate acceptance gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import signal
import sys
from types import FrameType

from check_installed_examples import (
    CheckError,
    Driver,
    executable,
    peer_controller,
    peer_helper_source,
    provider,
    require,
)


def run(binary: Path, plugins: Path, base: Path, expected_sha256: str) -> Path:
    """Retain native same-path A/B proof below base using the reviewed helper bytes."""
    import tempfile

    selected_path, source = peer_helper_source(plugins)
    digest = hashlib.sha256(source).hexdigest()
    require(digest == expected_sha256, "selected helper differs from reviewed handoff")
    root = Path(tempfile.mkdtemp(prefix="peer-identity-", dir=base)).resolve()
    checkout = root / "selected-plugins"
    helper = checkout / "tests/namespace_peers.py"
    helper.parent.mkdir(parents=True)
    helper.write_bytes(source)
    witness = root / "source-B-executed"
    anchor = b"from __future__ import annotations\n"
    require(source.count(anchor) == 1, "actual helper needs one future-import anchor")
    replacement = source.replace(
        anchor,
        anchor
        + b"from pathlib import Path as _WitnessPath\n"
        + f"_WitnessPath({str(witness)!r}).write_text('B executed')\n".encode(),
        1,
    )
    driver = Driver(binary, checkout, root, "actual-helper")
    require(driver.peer_helper.sha256 == digest, "driver did not load captured A")
    loaded = driver.peer_helper
    require(
        peer_controller(checkout) is loaded, "unchanged helper class was not reused"
    )
    try:
        with provider() as server, driver.peers([server]):
            transport = driver.transport
            temporary = helper.with_suffix(".replacement")
            temporary.write_bytes(replacement)
            temporary.replace(helper)
            result = driver.cli("runs", "list")
            require(result.returncode == 0, "actual fixture CLI failed")
            require(
                helper.read_bytes() == replacement,
                "temporary pathname no longer contains replacement B",
            )
            require(not witness.exists(), "replacement B executed during active scope")
            require(
                driver.peer_helper is loaded,
                "active controller changed its loaded implementation identity",
            )
            require(
                not server.requests, "identity check unexpectedly called a provider"
            )
        require(not witness.exists(), "replacement B executed during cleanup")
        for label, operation in (
            ("next-scope", lambda: driver.peers([]).__enter__()),
            ("next-driver", lambda: Driver(binary, checkout, root, "after-drift")),
        ):
            try:
                operation()
            except CheckError as error:
                require(
                    "source changed" in str(error), "unclear source-drift rejection"
                )
            else:
                raise CheckError(f"helper drift did not reject {label}")
        identity = json.loads((driver.root / "peer-helper-1.json").read_text())
        require(
            identity == {"path": str(helper), "sha256": digest}
            and json.loads((driver.root / "peer-helper.json").read_text()) == identity,
            "workflow receipts mislabeled the selected loaded A",
        )
        controller_receipt = driver.root / "namespace-peers-1.json"
        receipt = json.loads(controller_receipt.read_text())
        require(
            receipt["helper_sha256"] == receipt["controller_source_sha256"] == digest,
            "actual controller did not execute A",
        )
        require(
            receipt["cleanup_errors"] == []
            and receipt["error"] is None
            and receipt["owned_live_processes"] == []
            and receipt["caller_namespace_unchanged"]
            and not receipt["controller_alive"],
            "actual helper cleanup did not settle",
        )
        for key in (
            "handlers_remaining",
            "listeners_remaining",
            "namespace_fds_remaining",
            "pidfds_remaining",
            "control_fds_remaining",
            "source_fds_remaining",
            "pending_jobs",
        ):
            require(receipt[key] == 0, f"actual helper leaked {key}")
        child_reports = receipt["native_cleanup_reports"]
        require(
            receipt["supervisor_source_sha256s"] == [digest],
            "actual child supervisor did not attest to captured A",
        )
        require(
            len(child_reports) == 1
            and all(
                child["source_sha256"] == digest
                and child["remaining"] == []
                and not child.get("ownership_uncertain")
                for child in child_reports
            ),
            "actual child cleanup/source receipt differs from captured A",
        )
        report = {
            "platform": sys.platform,
            "selected_helper": str(selected_path),
            "temporary_helper": str(helper),
            "loaded_sha256": digest,
            "replacement_sha256": hashlib.sha256(replacement).hexdigest(),
            "replacement_witness_absent": not witness.exists(),
            "temporary_path_contains_B": True,
            "controller_receipt": str(controller_receipt),
            "workflow_identity": identity,
            "cli_returncode": result.returncode,
            "next_scope_drift_rejected": True,
            "next_driver_drift_rejected": True,
            "transport_class_module": type(transport).__module__,
            "cleanup_confirmed": True,
            "supervisor_digests": receipt["supervisor_source_sha256s"],
            "actual_child_receipts": child_reports,
            "acceptance_scope": "Focused actual-helper source identity only",
        }
        (root / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"PASS actual helper source identity: {root}", flush=True)
        return root
    finally:
        driver.close()


def deadline(_signal: int, _frame: FrameType | None) -> None:
    """Raise within the active helper so its bounded abort cleanup still executes."""
    raise TimeoutError("focused helper identity exceeded its 35-second deadline")


def main(argv: list[str] | None = None) -> int:
    """Run the explicit native check, failing on missing prerequisites or a hang."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transist", required=True, type=Path)
    parser.add_argument("--plugins-dir", required=True, type=Path)
    parser.add_argument("--fixture-base", required=True, type=Path)
    parser.add_argument("--helper-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        require(sys.platform in {"linux", "darwin"}, "native Linux or macOS required")
        require(
            args.fixture_base.is_absolute()
            and args.fixture_base.is_dir()
            and not args.fixture_base.is_symlink(),
            "fixture-base must be an existing absolute nonsymlink directory",
        )
        binary = executable(args.transist, "transist")
        previous = signal.signal(signal.SIGALRM, deadline)
        signal.alarm(35)
        try:
            run(binary, args.plugins_dir, args.fixture_base, args.helper_sha256)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        return 0
    except (CheckError, OSError, ValueError, RuntimeError) as error:
        print(f"Peer helper identity incomplete: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
