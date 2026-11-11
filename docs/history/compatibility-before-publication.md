# Historical compatibility and validation

Archived development evidence; not acceptance of the public release baseline.

The publication target is the **0.12.0 public-beta runtime line**, not a stability
promise. Workflow schema `transist.flow.v1` and module schema
`transist.module.v1` are format identifiers. Package versions are independent of
runtime versions.

## Current local acceptance target

| Component | Committed local revision | Git tree |
| --- | --- | --- |
| Runtime (`transist-ai/transist.oss`) | `e3548d48a83ca01f34b12b7e69b9c06a8ea0c33b` | `f6b76f6d04ea832e3d2384dad04651e732b635b1` |
| Plugins (`transist-ai/transist-plugins`) | `64f79644436350329f2e893c6ca85f84eb6c91c0` | `06910cde41e4fdd27e2233636a75a3d5c26437ea` |
| Workflows (acceptance baseline) | `ad8bbd49f407eebab6da71b567830f7d0cf973ca` | `d920b386913801aff2b0afe21abb50ff6333dccc` |

These commits are local and **unpushed**. The unfiltered installed-example gate
passes all four maintained examples and all three synthetic authoring fixtures:
35 root runs on each of native Linux arm64 and Apple Silicon macOS against the
same M5 source tuple.
[Step 12 evidence](revised-workflow-authoring-step-12.md) records platform timings,
matching binary/helper identities, source freeze and cleanup outcomes. Binaries
were built before commit from source trees matching the committed trees above;
subsequent documentation edits do not redefine that tested baseline.

Workflow/module releases and plugin pins remain `0.1.0`; schemas remain `v1`,
runtime/admin `0.12.0`. Use fresh homes without replacing same-version payloads.
The manual compatibility CI job retains its **older provisional tuple**, listed in
[validation tooling](../../scripts/README.md), and
requires publicly fetchable exact commits. Do not substitute these unpublished
local SHAs into CI, or silently select `main`, a tag or another binary. Local
acceptance establishes neither public fetchability nor a release, authenticated
live-provider acceptance or governed publisher distribution.

[Step 9](revised-workflow-authoring-step-9.md),
[Step 10](revised-workflow-authoring-step-10.md) and
[Step 11](revised-workflow-authoring-step-11.md) retain their implementation-time
source identities, targeted outcomes and then-pending gates as historical records.

Build the runtime with its checked-in toolchain and lockfile:

```sh
cargo build --locked -p transist-cli --bin transist -p transist-admin --bin transist-admin
```

The validator requires an explicit executable reporting `transist 0.12.0`.
Version output alone does not prove source provenance. Build matching runtime and
admin from the same reviewed source bytes before fixtures; both retain runtime version
`0.12.0`. [Step 12 evidence](revised-workflow-authoring-step-12.md) records the
accepted native binaries and source-freeze identity.

## Example identities and dependencies

| Workflow | Exact plugins |
| --- | --- |
| `edge_fault_advisory@0.1.0` | `shell@0.1.0`, `openai.compatible@0.1.0` |
| `ai_agent_plugins_canary@0.1.0` | `anthropic`, `cursor.cli`, `github.copilot.cli`, `ollama.cli`, `opencode.cli` at `0.1.0` |
| `cursor_ticket_delivery@0.1.0` | `cursor.cli`, `git.cli`, `github.cli`, `jira.rest`, `openspec`, `shell` at `0.1.0` |
| `hotfix_ticket_delivery@0.1.0` | `git.cli`, `github.cli`, `github.copilot.cli`, `jira.rest`, `shell` at `0.1.0` |

Workflow YAML is authoritative. Changed executable bytes require a new digest
and corresponding signature; never overwrite an existing immutable installation.

All authored roots, module releases and plugin pins are deliberately fixed at
`0.1.0`; the `v1` schema identifiers are unchanged. Current source includes lean
model contracts, bounded scanners and working-file guards. Reviewed governed
packaging remains required; existing signed packages under `packages/` are
separate bytes. The `1.0.0` lifecycle, signature and installation evidence below
is historical and does not validate the new source bytes.

Compact CLI/OpenSpec inputs require the corresponding plugin action schemas.
The current unfiltered installed gate validates all four examples and all three
authoring fixtures in fresh homes against the local tuple above, including real
source checks, deterministic explanations and installed execution with fake peers.
Offline graph tests alone establish containment and exact pins, not schema
compatibility or runtime execution success.
These checks do not establish live-provider or governed invocation acceptance;
no Transist trust signing or operational installed-package replacement is performed.

No payload checksum inventory, vendored plugin contracts or signature sidecars
are tracked in this source repository. The public snapshot gate enumerates its
current inclusion list. Newly packaged `0.1.0` bytes require new digests and
administrator signatures; historical packages under ignored `packages/` are
rollback evidence, not a distribution of this reset. The provisional compatibility
CI pins are an older source target, separate from current local installed
acceptance; neither tuple is evidence of a published signed distribution.

Python 3.10+ and the pinned development dependencies support the checks. The
validator always builds Ollama's adapter from complete reviewed Go source in
disposable staging; it ignores existing build outputs. The real Go toolchain must
be on `PATH`; macOS also requires Apple's C SDK/compiler and native ad-hoc Mach-O
sealing. Build receipts record source/toolchain/output identities. This OS
executable sealing uses no key and is not Transist package signing. The builder
does not modify the original plugin checkout. Static checks discover declared
prerequisite executables and fail if missing, but do not launch agents, contact
providers or require authenticated CLI sessions/model servers. Installed fixtures
supply explicit deterministic fake provider executables.

## What checks establish

- Snapshot checks: allowed paths, byte-pattern privacy checks and local links.
- Offline tests: helper behavior and fail-closed readiness/gate handling.
- Runtime source checks: the full module/asset graph and representative bound
  action contracts in fresh homes, without runs or external dispatch.
- Installed fixtures: real installed plugins and sandbox/store/gate paths, exact
  document/provider bytes, all five canary participants, delivery recovery and all
  three authoring fixtures under fake external CLI/HTTP boundaries. The full
  unfiltered matrix passes on native Linux and macOS. No real credentials.
- Deterministic explanation snapshots: projections of actual CLI JSON, regenerated
  twice against installed contracts. Explanation is not readiness or consent.

Static checks deliberately exclude live secret values and mutable external
state. They do not prove model availability, authentication, GitHub approvals,
network reachability or governed trust. Readiness must be checked separately in
the intended runtime home before execution. Credentialed integration tests are
not part of public CI.

## Cursor lifecycle remediation record (2026-10-07)

- Runtime lifecycle source: `8ad853f`; baseline: pre-fix `6eed168`.
- Companion source: `825beba` plus native installed-fixture corrections. The
  package version recorded then was `1.0.0`. Existing lifecycle evidence remains a
  historical record and does not independently verify current package bytes;
  real-provider behavior is a separate gate.
- All four public examples pass unbound and representative-bound source checks.
  Complete workflow tests pass: 58 root, 30 Cursor helper and 11 hotfix helper
  tests; formatting, lint and publication checks pass.
- Publisher signatures for Cursor `1.0.0` and canary `1.0.0` verify. All five
  exact signed dependencies and the signed workflow installed in an isolated
  governed home; installation created no run and changed no production home.
- Overall remediation acceptance remains pending: the companion full static
  gate reports three pre-existing checksum matches in its model-lock fixture,
  and the governed live Cursor invocation has not been executed from an
  authorized account-state environment. Do not infer live acceptance from static
  checks or signed installation.
