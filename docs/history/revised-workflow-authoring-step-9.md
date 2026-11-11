# Revised workflow authoring — Step 9

## Scope and identities

Only the introductory edge advisory and five-participant canary are migrated.
Workflow/plugin releases remain `0.1.0`; runtime/admin remain `0.12.0` and schema
identifiers remain unchanged. Work is on local `main`; final independent review
verified the execution boundary, profile parity, negative checks and explanations.
The original plan ledger records the Step 9 commit after verification.
No sibling source or preserved generated package is edited.

| Component | Reviewed source |
| --- | --- |
| Workflows baseline | `88e6871cd8155b2d021e8fc1420685b273b7e5ea` plus this Step 9 diff |
| Runtime/admin, Step 8 | `48b1d9aaf7b0f56d20eae73cd9068312dcae8771` |
| Plugins, Step 7 | `be895a6ca0cf406fba5d33b96485a67e2269f9c8` |

Matching runtime **and admin** were built from the clean Step 8 checkout before
installed fixtures. Version strings alone are not source provenance:

| Binary | SHA-256 |
| --- | --- |
| `transist` | `8f67f25e31a54dd8a45342ea56f5cd00e7d14faa5f894dac576680ecdf699861` |
| `transist-admin` | `dd99dc9ca20f5bec126e3b8fb15514be009c92172ac7075368493da36f2dee5e` |

Logs and retained fixtures: `projects/tmp/revised-authoring-step-9-validation/`
(outside the published source snapshot). Environment: Darwin 24.6.0, arm64;
Python 3.14.6 virtual environment with the `requirements-dev.txt` pins (full freeze
in `environment.log`); Go 1.22.5, Rust 1.88.0 checked-in toolchain/lockfile.
`PYTHONPATH` is unset. Rust `TMPDIR` is project
scratch; Python/Go caches/temp storage are isolated. Linux/final acceptance remains
Step 12.

## Implementation

- Advisory: workspace `shell/read_file` capture → managed `diagnostic` → manual
  gate `review_documents` → exact `reviewed_by: diagnostic_transfer` file read by
  OpenAI-compatible chat → managed `response`. The role/instructions use the
  action's actual literal `system_prompt` contract, not an unsupported prompt-file
  binding. Destination, port/TLS/no-redirect authority and logical secret stay
  literal and explicit. No duplicated diagnostic input or launcher pre-read.
- Launcher: default source validation; `--execute` separately selects installation,
  live readiness and capture/start. It never approves a real gate. Workspace/file
  inputs are selected without pre-reading contents. Response documentation uses
  committed revision metadata and managed-document content inspection.
- Canary: immutable context and exact action-bound profiles factor prompt/lean
  settings. All five participants, actions, order, supported budgets/history,
  credentials, usage/lifecycle and authored network/filesystem scope are retained.
  Native Anthropic/Ollama contracts do not acquire fictional OpenAI file settings.
- Source checker: only runtime-reported payload dependency/schema findings accept
  `deferred_to_dispatch`. Authority/secrets/prerequisites and known fields remain
  checked. Actual malformed/unknown selectors and missing script assets fail.
- Installed checker: explicit finite inventory and repeated selectors; explicit
  runtime/admin/plugin checkout/base. Delivery entries and unfiltered execution
  fail as pending Step 10 instead of falsely passing reduced coverage. No required
  fixture skips, real provider credentials or operational homes.
- Explanations: actual CLI JSON is generated twice per original source; identical
  portable projections match checked-in `explanation.txt`. Raw JSON with complete
  contract/payload digests remains in the fixture evidence. Human requests and
  expected results lead both example READMEs.

Every installed plugin is the complete selected payload, byte-compared with its
staging source, with per-file digest receipts. Ollama always builds from an explicit
complete non-test Go inventory in fresh scratch, ignoring ignored binaries. On
macOS its native observer requires cgo. Go 1.22 with the current Apple linker left
an invalid Mach-O ad-hoc signature (initial handshake exited SIGKILL); the builder
now seals and verifies only its new scratch executable with keyless OS ad-hoc
signing. This is not a Transist trust signature. Retained build receipts record
toolchain, source digests, exact command, cgo, native sealing and output digest.

Fixture workflow copies change identity and narrow provider networking to fake
CLI/no egress or the exact loopback HTTP port. Plugin handlers, APP handshake,
schemas, parsing, file I/O, publication, sandbox and lifecycle remain real. Nothing
replaces an installed same-version payload. Existing signed packages are immutable
rollback material; no new governed/production-signature claim is made.

## Targeted commands and outcomes

From the workflows repository, use the retained pinned virtual environment as
`$PYTHON`, the tuple's built binaries as `$TRANSIST_BIN` / `$ADMIN_BIN`, the explicit
sibling checkout as `$PLUGINS_DIR`, and the retained evidence base as `$VALIDATION`.
Prepend the real Go toolchain and pinned venv bin directories to `PATH` (a home-
dependent version-manager shim is insufficient in isolated homes).

```sh
# In the clean runtime checkout, before fixtures:
env -u PYTHONPATH TMPDIR="$PROJECT_TMP" cargo build --locked \
  -p transist-cli --bin transist -p transist-admin --bin transist-admin

env -u PYTHONPATH "$PYTHON" -B scripts/check_examples.py \
  --transist "$TRANSIST_BIN" --plugins-dir "$PLUGINS_DIR" \
  --home-base "$PWD/tmp" \
  --example edge_fault_advisory --example ai_agent_plugins_canary

env -u PYTHONPATH "$PYTHON" -B scripts/check_installed_examples.py \
  --transist "$TRANSIST_BIN" --admin-bin "$ADMIN_BIN" \
  --plugins-dir "$PLUGINS_DIR" --fixture-base "$VALIDATION" \
  --example edge_fault_advisory --example ai_agent_plugins_canary

env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s tests -p 'test_check*.py' -v
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s tests -p test_edge_runner.py -v
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s tests -p test_public_snapshot.py -v
```

| Targeted check | Outcome | Retained log |
| --- | --- | --- |
| Matching runtime/admin build | pass | `build.log`, `environment.log` |
| Two selected source checks, unbound + representative bound | pass | `source-final.log` |
| Two selected installed examples, six runs | pass, zero skips | `installed-final.log` |
| Stronger fully bound source negatives + advisory rerun | pass, four advisory runs | `installed-edge-source-regressions.log` |
| Source/installed checker unit cases | 42 pass | `checker-units-final.log` |
| Edge launcher/readiness/review unit cases | 7 pass | `edge-units-final.log` |
| Affected publication-checker cases | 17 pass | `snapshot-checker-units-final.log` |
| Actual launcher default with empty credential environment | source-only pass, no run | `launcher-validation.log` |
| Black check, nine affected Python files | pass | `format-final.log` |
| flake8, same nine files, 88-column limit | pass | `lint-final.log` |
| Selected file/privacy/local-link checks, 21 changed/new files | pass | `docs-selected-final.log` |
| Diff whitespace check | pass | `diff-check-final.log` |

The main installed fixtures are `edge-9jp9054o/` and `canary-xtuxm_0l/`; the final
fully bound source-negative/advisory refinement is `edge-y1v18x7q/`. Each retains
numbered JSON command transcripts and full/raw explanation evidence. Canary also
retains `ollama-build-receipt.json` and per-file plugin payload hashes. Its native
Ollama binary SHA-256 is
`8c87c4e3d2bbfe604929ad70d4a033a3656a6dfaf7951231eb127273db117ec3`.
The negative-source fixture first proves the valid document flow passes with
actual `deferred_to_dispatch` findings, then supplies all required inputs to the
unknown-step, malformed-selector, unknown-prior-variable and missing-script
cases. Failures cannot be explained by an omitted required input.

The selected docs check invokes the existing `check_public_snapshot.check_file`
only for the 21 changed/new paths, using its current candidate inclusion set; it
does not run the unfiltered snapshot gate. Black/flake8 use exactly the nine changed
Python paths. No full repository, delivery, aggregate CI or security gate ran.

Retain failed attempt logs as diagnosis, not acceptance. Earlier attempts caught a missing
noninteractive install flag, use of `runs resume` rather than `runs start` for a
blocked run, omitted tool paths, invalid native Mach-O sealing and an incomplete
fake Anthropic response; those fixtures were repaired without sibling changes.

Installed advisory assertions cover four runs: approved, rejected, restarted at
the waiting gate, and a genuine new publication after approval. All pause with
zero provider calls; approval/restart each allow one call with exact reviewed
UTF-8, CRLF and whitespace plus the literal system role. Rejection and changed
revision allow zero. Workspace changes after capture never replace reviewed
bytes. Successful responses become managed revisions with retained usage. The
full request/history-tampering matrix remains runtime Step 5's tested contract.

Canary assertions cover two fresh runs of all five participants, supported
compact/history/prompt budgets, exact fake responses, available token usage, real
subprocess lifecycle and an unchanged workspace.

## Review and rollback

Parent review and commit remain pending. Revert this Step 9 diff to select the
preceding example sources; retain prior immutable packages/homes. No home-format
migration or external real-provider effect needs reversal. Delivery migration is
Step 10; complete repository/Linux/macOS gates remain Step 12.
