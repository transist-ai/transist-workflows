# Revised workflow authoring — Step 12

**Local installed acceptance: pass on native Linux arm64 and Apple Silicon macOS.**
The full unfiltered `scripts/check_installed_examples.py` invocation passes all
four maintained examples and all three synthetic authoring fixtures on each OS.
This records local fake-peer acceptance, not public fetchability, a release,
authenticated live-provider acceptance or governed publisher distribution.

## Accepted source identity

| Component | Committed local revision | Git tree |
| --- | --- | --- |
| Runtime/admin | `e3548d48a83ca01f34b12b7e69b9c06a8ea0c33b` | `f6b76f6d04ea832e3d2384dad04651e732b635b1` |
| Plugins | `64f79644436350329f2e893c6ca85f84eb6c91c0` | `06910cde41e4fdd27e2233636a75a3d5c26437ea` |
| Workflows | `ad8bbd49f407eebab6da71b567830f7d0cf973ca` | `d920b386913801aff2b0afe21abb50ff6333dccc` |

All three commits are **local and unpushed**. The binaries were built before commit
from trees matching these committed trees. Later documentation edits do not change
the acceptance baseline. Source-freeze manifest SHA-256:
`627741d28ae9e90aabbb2d7a269b61d8a2a3450e0a8438da5b24a6a12923a43a`.

| Native binary | SHA-256 |
| --- | --- |
| macOS `transist` | `571d2599fab3c216af1717014e13cf1619ff84f7d8b729d013745a7c09048a2a` |
| macOS `transist-admin` | `b119daba383827cf86419c7575cfc8be8300de85a68dc78532191cb4a5819836` |
| Linux `transist` | `9bcbaedc133ddd8548e9f1b7c3f9cde5f49976d9dc3665b087f589dd7a73709e` |
| Linux `transist-admin` | `f741eb87802cd5f0d23702398296c5dc9314999af1b722819a465996a4e49c12` |

Loaded peer-helper SHA-256:
`046c01bcd139d7ac75654045ff179e65f1403028ec6a88cc4c70ae6e68d600e2`.
Runtime/admin report `0.12.0`; workflow/module releases and exact plugin pins remain
`0.1.0`, schema identifiers `transist.flow.v1` / `transist.module.v1`. Fresh homes
install exact selected payloads without overwriting same-version installations.

## Full native matrix

Both runs used the same M5 source tuple; Linux ran in a native Debian 12 arm64 VM.

| Platform / sandbox | Result | Elapsed | Outer deadline | Idle deadline |
| --- | --- | --- | --- | --- |
| Debian 12 arm64 / bubblewrap | Complete pass | 2208.90 s | 2400 s | 300 s |
| Apple Silicon macOS / sandbox-exec | Complete pass | 3729.22 s | 7200 s | 300 s |

| Required inventory | Root runs per OS |
| --- | --- |
| Edge fault advisory | 4 |
| Agent plugin canary (all five participants) | 2 |
| Cursor ticket delivery | 11 |
| Hotfix ticket delivery | 8 |
| Three conversational authoring fixtures | 10 |
| **Total** | **35** |

- Both unfiltered commands completed successfully; no selected subset or partial
  receipt substitutes for the full inventory.
- Cursor covers all four accepted-reply/lost-response combinations: conversation
  and review thread, each through real retry and resume, without duplicate posts.
- The compiler, installed plugin handlers/contracts, document store, manual gates,
  sandbox and recovery are real. External model, service and publication peers
  are deterministic fakes; local Git operations are real in synthetic workspaces.
  Synthetic fixture decisions are not evidence of human execution approval.
- macOS finished with all 24 controller receipts complete, zero resources, zero
  owned live processes and zero ownership uncertainty. Both native runs recorded
  `source_after_guard: 0`.
- The earlier macOS attempt with a 2400-second outer deadline was **incomplete**,
  not a pass. The successful rerun changed only that outer deadline to 7200 seconds;
  inner, cleanup and resource limits were unchanged. Keep the earlier attempt as
  diagnostic history.

## Evidence and reproduction

Retained evidence inventory: source-freeze manifest; native binary and loaded-helper
digests; full command/exit/timing records; per-root provenance, installed payload
fingerprints, source checks and deterministic explanations; immutable reviewed
document revisions; fake-peer publication/recovery observations; runner/controller
cleanup receipts; and both post-run source guards. Raw logs and runtime homes stay
outside the public snapshot. No operational credentials or signing material are
part of this acceptance.

From the workflows repository, use explicit reviewed native binaries, the matching
plugin checkout, a Python environment with the pinned development dependencies on
`PATH`, and an existing absolute disposable `FIXTURE_BASE` outside target Git
workspaces. Retain stdout/stderr and the outer supervisor's status there:

```sh
env -u PYTHONPATH "$PYTHON" -B scripts/check_installed_examples.py \
  --transist "$TRANSIST_BIN" --admin-bin "$ADMIN_BIN" \
  --plugins-dir "$PLUGINS_DIR" --fixture-base "$FIXTURE_BASE" \
  > "$FIXTURE_BASE/installed-examples.log" 2>&1
```

Omit all example/fixture selectors. Use the platform-specific outer/idle budgets
above without relaxing runtime or cleanup limits. Missing prerequisites, scenarios
or complete cleanup are failures. Preserve fresh homes and receipts for review.

## Authoring and publication boundaries

- Managed file/tree intermediates stay outside Git. Process-only `read`, `write`
  and `update` bindings replace shared workspace paths; successful batches publish
  immutable revisions. Source/OpenSpec deliverables remain in the repository.
- Typed `steps.<id>.out` values and module outputs carry data/control. Read exports
  only after child success. `reviewed_by` names the exact lexical gate step and
  protects revision ID plus digest; it does not approve arbitrary workspace edits.
- Never add Git ignores to hide operational data. Resume preserves committed
  documents; replay starts a fresh namespace. Neither reverses external effects.
- [Historical compatibility](compatibility-before-publication.md) separates this local tuple from the older
  provisional manual-CI pins. Do not point CI at unpublished commits or infer
  signed publisher distribution from fake-peer installation.
- The exact report path is in the publication gate's `DOC_FILES` inventory;
  publication still requires the current privacy/path/link checks.

[Step 9](revised-workflow-authoring-step-9.md),
[Step 10](revised-workflow-authoring-step-10.md) and
[Step 11](revised-workflow-authoring-step-11.md) remain historical records; their
then-pending native/full-matrix gates are resolved by the local evidence above,
not by rewriting past results. Preserve immutable homes/packages for rollback;
source rollback does not rewrite history or undo Git/service effects.
