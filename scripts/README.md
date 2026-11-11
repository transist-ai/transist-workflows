# Publication and static example checks

Install `requirements-dev.txt` in a disposable Python environment (Python 3.10+).

```sh
python scripts/check_public_snapshot.py
python scripts/check_public_snapshot.py --list
python -m unittest discover -s tests
python scripts/check_examples.py --transist /absolute/path/to/transist --plugins-dir /absolute/path/to/public-plugin-checkout --home-base /tmp
```

Run example helper tests separately, where supplied:

```sh
python -m unittest discover -s examples/hotfix_ticket_delivery/tests
python -m unittest discover -s examples/cursor_ticket_delivery/tests
```

The snapshot gate enumerates current tracked and nonignored untracked files,
including staged-but-missing files. It never reads history, recursively walks
excluded trees, copies files, or publishes. A tracked excluded file fails before
reading its contents. `--list` emits no inclusion list on failure. Diagnostics
name safe allowed public paths; rejected or sensitive paths use opaque candidate
IDs. Sensitive source matches are never exposed.
Only the explicitly allowed root files, enumerated public documents, CI/template files,
scripts, tests, and four example trees can enter the reviewed snapshot. Relative
Markdown links must resolve to files or directories represented in that snapshot.
The gate is a content review aid, not proof that arbitrary secrets are absent.

The example checker requires **Transist 0.1.1** and exact plugin versions from
`plugins/<id>/plugin.yaml` in the explicit public checkout. It checks every
declared module, assets, metadata, conflicting pins and duplicate IDs.
Control expressions reject unsupported word-form `and`/`or` operators; use
`&&`/`||` instead. Quoted values and dotted reference names are unaffected. Genuine
runtime source checks validate graph/action schemas, first unbound, then with
published sample inputs adjusted to synthetic workspaces. Each example gets its
own disposable standalone home and user/config/temp directories. No credentials
are inherited or fabricated. It never invokes agents, adapters, Transist signing,
installed-workflow readiness probes, or execution commands. Source files remain
read-only; only newly created disposable directories are removed on exit.
Action schemas may use transitive, selected, contained local references; external
schema resolution is refused before installation to keep validation offline.
The initial catalog baseline uses `0.1.0`. After publication, workflow and module
releases can advance independently using SemVer, including prerelease and build
metadata; root plugin pins must be exact SemVer identities, not ranges or floating
references. Published versioned payloads are immutable: changed bytes require a
new version and, for signed packages, a new signature. Validate new packages in
fresh disposable homes and retain prior bundles and homes for recovery; never
replace an installed payload. Schema identifiers remain `transist.flow.v1` and
`transist.module.v1`.

The example checker validates exact SemVer identities and requires selected plugin
manifests to match their pins. Validation of a later release requires its exact
dependencies and fresh evidence; a rejection is not a passing check.
Cleanup actions/assets and module-call step IDs participate in graph checks.
Use repeatable `--example <name>` to check a subset; missing selected roots still
fail. Without that option all four named roots are required.

Synthetic negative/version-policy fixtures exercise invalid metadata and inexact
pins; the third-party `v1.0.0` requirement in the negative stdlib-only Ollama build
fixture is not a Transist catalog release or pin. The edge advisory launcher's
dependency boundary remains tied to its selected `shell@0.1.0` package.

Run the focused release-policy checks with:

```sh
python3 -B -m unittest discover -s tests -p 'test_version_policy.py' -v
```

Dependency packages are staged from the complete real `package.files` selection.
Missing files fail, except the documented `ollama.cli` output `bin/ollama.cli`:
that adapter is always rebuilt from real `go.mod` and the explicit complete
non-test Go source inventory under `cmd/plugin/` in
disposable scratch storage, with no third-party dependencies or substitute binary.
Go must be discoverable as an absolute executable using `shutil.which` on PATH.
Point PATH at the real Go toolchain if a version-manager shim depends on the
original user home. `GOPROXY=off`, `GOSUMDB=off`, `GOTOOLCHAIN=local`, and isolated
Go cache/temp/module directories keep the build offline. macOS uses cgo, Apple's
C SDK/compiler and `/usr/bin/codesign` to seal the fresh scratch Mach-O executable
ad hoc (no key; not a Transist package signature). Build stdout/stderr and a source,
toolchain, command and output-digest receipt stay in scratch. Ignored binaries
are never substituted for a reviewed source build. The source checkout is
never changed. Only PATH is retained from the host for static prerequisite
discovery; all other environment settings are constructed explicitly.
The disposable user home contains `.cursor`. Only the scratch standalone
config's process secret-delivery policy is enabled, via PyYAML, for metadata
validation; HTTP/MCP delivery settings are preserved and no secret is supplied.
Missing secrets and failed runtime checks are **incomplete**, with nonzero exit,
not passes. Static checks intentionally do not establish live integration readiness.
Representative-bound checks require passing static binding and authority evidence;
only `secret_value` and `external_state` may remain `not_evaluated`. The actual
compiler's `deferred_to_dispatch` findings are accepted only for payload dependency
codes `step_output`, `mutable_variable`, `input_schema` and `deferred_to_dispatch`.
Authority, grants, secret references and known payload fields are still checked;
warnings, failed/malformed references and other incomplete checks block. This
does not turn dispatch-time schema checks or provider probes into static passes.
Transist 0.1.1 on macOS protects the whole `/private/tmp` tree from external
filesystem grants. A workflow grant to `~/.cursor` therefore overlaps that
protected root when the isolated user HOME is under `/tmp`. On macOS use
`--home-base "$PWD/tmp"` from the repository root instead. The repository's
ignored `tmp` directory (or a selected child beneath it) must already exist and
all its path components must be regular nonsymlink directories. The checker
creates and removes only its own disposable child, not the approved base.
No workflow grants or sandbox policy
are changed, and the real user HOME is never used. The default remains `/tmp`;
Linux local validation can use it because the protected temporary root follows the
isolated `TMPDIR`, separate from the disposable user HOME.

## Installed examples

```sh
python -B scripts/check_installed_examples.py \
  --transist /absolute/path/to/transist \
  --admin-bin /absolute/path/to/matching/transist-admin \
  --plugins-dir /absolute/path/to/transist-plugins \
  --fixture-base /absolute/disposable/fixture-storage \
  --example edge_fault_advisory --example ai_agent_plugins_canary
```

Existing checker arguments `--transist`, `--plugins-dir`, `--home-base` and
repeatable `--example` work (`--home-base` aliases `--fixture-base`). Explicit
matching runtime/admin binaries and an existing absolute fixture base are required;
`--transist-bin` and `--transist-admin` are binary-argument aliases. Version checks
require 0.1.0, while printed binary digests and the verified release record establish
the intended source tuple. Admin is checked for provenance; this runner performs
no Transist signing/private-key operation.

The finite inventory registers required runners for all four maintained examples.
Repeated selectors run once; unknown/missing runners and failed scenarios return
nonzero. `--list` reports inventory only, never execution success. During Step 10
both delivery examples were selected separately. Current acceptance is recorded in
[validation](../docs/validation.md). The required **unfiltered** command covers all
four examples plus all three authoring fixtures on both native platforms. To run
the full gate, omit every `--example` selector from the command above. Selected runs
remain useful diagnostics but cannot substitute for that inventory.

### Conversational authoring fixtures

```sh
python -B scripts/check_authoring_fixtures.py --transist "$TRANSIST_BIN" \
  --admin-bin "$ADMIN_BIN" --plugins-dir "$PLUGINS_DIR" --fixture-base "$VALIDATION"
python -B -m unittest discover -s tests -p test_conversational_authoring.py -v
```

An existing absolute disposable `--fixture-base` and explicit matching 0.1.0
binaries are required. Repeatable `--fixture` selects diagnostic_advisory,
approved_draft_publication or two_approval_revision; `--list` lists inventory only.
Without selectors all three are required. The unfiltered
`check_installed_examples.py` also calls this whole inventory after its four
maintained examples; the full acceptance gate cannot silently omit authoring coverage.

Definitions live under `tests/fixtures/conversational_authoring`, not new
`EXAMPLES` roots. Each has portable inputs, contained inline prompts, a recorded
synthetic assistant walkthrough and mandatory real-runtime scenarios. Source
validation/explanation remain read-only; test installation and fake execution are
separately authorized fixture setup. Exact installed payloads/contracts, missing
pre-start inputs/pins, deterministic explanation, intended-only revision diff,
exact reviewed bytes, distinct sequential approvals, reject-either and real
changed-revision blocking are required. External model transport and `gh` are
deterministic fakes; the compiler, plugins, sandbox, documents and gates are real.
Every owned runner/listener must exit. No skips or same-version overwrites.
See [fixture inventory](../tests/fixtures/conversational_authoring/README.md) and
[historical Step 11 evidence](../docs/history/revised-workflow-authoring-step-11.md).
The current full native matrix is recorded in
[validation](../docs/validation.md); synthetic gate decisions
do not represent human execution approval.

Fresh retained homes install selected real package payloads once and compare every
installed byte with staging. Ollama is rebuilt from the explicit reviewed source
inventory, never taken from an ignored same-version build. Fixture transcripts,
full CLI explanations, portable projections, per-file payload hashes, Go build
receipts and fake-provider observations remain below the selected base. No user
credentials/configuration are inherited. External CLI executables are fake;
OpenAI-compatible and native Anthropic wire calls use local HTTP servers. Plugin
APP handlers, schemas, parsers, staging, sandbox, usage and subprocess cleanup are
real. Fixture workflow copies narrow CLI networking to none and redirect only
native HTTP to an exact loopback port; authored endpoint scopes remain explicit.
No package is overwritten and no existing home is reused. Delivery fixtures use
actual complete root/module/action graphs and captured helpers. Fixture identity,
networking and the explicit Linux tool-only grant below change in copied
definitions; service responses are deterministic. Native Git still executes all
local queries/staging/commits, while
fake network verbs and local Jira/GitHub/model peers avoid operational systems.
Every owned detached runner and local listener is settled before teardown.

Unexpected installed-checker failures also retain a mode-0600
`installed-failure-*.json` below the explicit fixture base. It records exception
type, numeric OS errno where available, and up to 32 stack locations (source
basenames, functions and line numbers). It deliberately omits exception messages,
OS filenames, subprocess arguments/output, source lines and frame locals. The
ordinary summary stays sanitized; failure to write diagnostics still exits nonzero.
Child-pidfd EINVAL failures also retain an allowlisted numeric process observation:
expected PID/birth, best-effort surrounding identities and procfs PID/TGID/PPID.
These non-atomic diagnostics never establish ownership or suppress the failure.
Up to eight related causes/contexts are captured with the same restrictions, so
cleanup failures cannot hide a primary syscall failure. Interrupts still propagate.
For ownership investigations, run the installed workflow gate without concurrent
Transist test batches on that host; retain its peer/runner cleanup receipts.
Darwin final cleanup may repeat a gap-only census within its existing cleanup
deadline, but requires a new complete snapshot before confirming cleanup.
Persistent gaps, unresolved lineage and permanent ownership uncertainty still fail.

Linux installed fixtures explicitly load the test-only
`tests/namespace_peers.py` helper from the selected `--plugins-dir` checkout;
missing helper or native setns/pidfd privilege is a failure, never a skip. Only
the finite existing loopback peers are bound inside owned invocation namespaces,
using the original handlers and shared observations. The controller does not
forward traffic, raise loopback, change routes or weaken the runtime sandbox.
Darwin retains its existing provider transport. Helper/shim hashes, native process
births, namespace/port identities and complete resource cleanup are retained.
Driver initialization captures and hashes the exact contained helper bytes, then
compiles those bytes without a loader reread or bytecode-cache substitution.
Unchanged drivers share the loaded class; changed helper source fails before a
new peer scope. `peer-helper.json` and numbered `peer-helper-<scope>.json` record
the **loaded** implementation's selected path and digest, never a later file's
digest. Restart the validation process after an intentional helper update.
The loader also retains those immutable bytes for the helper's explicit source
binding: native supervisors must execute that snapshot, never reopen a mutable
helper pathname while claiming its earlier digest.
Before module execution it supplies `__namespace_peers_source__` and
`__namespace_peers_expected_sha256__`, then verifies the helper's `SOURCE_BYTES`
and `HELPER_SHA256` binding. Helpers without that contract fail closed.

Run the focused actual-helper regression separately on native Linux and macOS:

```sh
python -B scripts/check_peer_helper_identity.py \
  --transist /absolute/path/to/reviewed/transist \
  --plugins-dir /absolute/path/to/reviewed/transist-plugins \
  --helper-sha256 "$REVIEWED_HELPER_SHA256" \
  --fixture-base /absolute/disposable/fixture-storage
```

It copies the whole selected helper into a temporary checkout, loads A, enters a
real peer scope, atomically replaces only that copy with a protocol-compatible B
execution witness, and dispatches the real isolated `runs list` CLI. Loaded and
supervisor digests, absent B execution, next-scope/driver drift rejection and
cleanup must agree. This creates no workflow run and invokes no provider; it is
source-identity integration evidence, not the full installed workflow matrix.
Use the helper owner's reviewed source-binding API and digest; the older
pathname-based supervisor implementation is not sufficient for this check.

Fake executables and Linux controller shims stay in one fixture-owned `bin`
directory outside every target Git worktree and managed document store. Linux
copies add only an exact read-only filesystem grant for that tool directory;
no parent path, operational data or write/network authority is added. No ignore
rule or workspace path is changed. Original source checks/explanations still use
the untouched authored definitions. Each delivery root has a separate controller
scope so all mandatory scenarios, independent roots and replay remain within the
finite transport budget.
All execution fixtures use the runner-owning driver and wait for detached runner
exit before acting on a durable blocked state, so approval never races the prior
runner's lease release.
Linux delivery setup also aliases the resolved **real native awk executable**
inside that same read-only tool directory. This avoids Debian's hidden
`/etc/alternatives` indirection without reopening `/etc`, changing the authored
shell helper or faking its output. `native-tools.json` records the executable's
path and exact hash; a missing native tool fails setup.

Advisory coverage: approval, rejection, restarting a waiting run with `runs start`,
and a real successful producer publishing a new diagnostic revision after approval.
The runner proves exact UTF-8/CRLF/whitespace reaches the provider only after
approval, zero external calls on rejection or changed revision, and managed
response publication. It separately changes the original workspace file to prove
that review covers the captured document rather than arbitrary workspace bytes.
Malformed/unknown step/variable references and a missing script fail genuine
source validation. Runtime Step 5's request/history-tampering matrix remains the
runtime's regression coverage; this does not duplicate its full suite.

Canary coverage: two installed runs of all five existing participants, exact fake
responses, compact output, invocation-only history and supported byte budgets,
usage where supported, and an unchanged workspace. Missing tools, fake-provider
prerequisites, schema failures or missing selected source fail; no skip is a pass.
This is deterministic installed acceptance, not live-provider or governed trust.

Introductory examples check in the portable `explanation.txt`. Delivery examples
check in `explanation.snapshot.json` with definition/projection fingerprints;
full JSON and text stay in retained evidence. All use `explanation_snapshot.py`
on actual CLI reports. Checks explain original source against real installed
contracts twice, require identical JSON, and compare text or its recorded digest.
Reproduce a portable snapshot with:

```sh
"$TRANSIST_BIN" workflows explain --path examples/edge_fault_advisory/workflow.yaml \
  --home "$AUTHORING_HOME" --format json | python -B scripts/explanation_snapshot.py
```

Use an explicit authoring home with matching installed plugins. Explanation
reads it without probing, writing, authorizing or executing; missing required
inputs stay visible. Full JSON retains package/schema digests; the portable text
omits platform-specific payload digests. [Historical Step 9 evidence](../docs/history/revised-workflow-authoring-step-9.md)
records targeted outcomes and the retained source/binary identities.

## Reproducible compatibility target

### Lean model inputs and local working-file checks

Cursor, Copilot and OpenCode canaries/delivery steps opt into `output_mode:
compact`, `history_mode: invocation`, a 65536-byte context-file limit and a
98304-byte prompt limit. OpenSpec uses the output and byte-limit fields without
CLI history; bound reviewer feedback uses `focused` mode. Ollama canaries use
compact output and the prompt limit supported by their authored action schema.
Native provider and shell actions receive no unsupported CLI fields. In
particular, the edge advisory uses bounded `shell/read_file` and a managed
diagnostic document; no stdout copy is its model input.

Historical Step 12 records an unfiltered installed fake-provider gate for four
examples and three authoring fixtures on native Linux and macOS; see
[historical Step 12](../docs/history/revised-workflow-authoring-step-12.md).
Those results apply only to the tested bytes and dependency tuple, not later
releases. Source/helper/graph checks alone do not imply runtime success. The older
selected-example results remain recorded in Steps 9–11; current acceptance is in
[validation](../docs/validation.md).

Delivery-owned `check_working_files.py` guards reject tracked or otherwise
stageable legacy operational files before generation and commits. Managed
documents live outside Git and require no exclusions. Guards never edit ignores.
The source scanner excludes operational files and its own output even when
tracked. It streams files with limits of 8 MiB/file and 64 KiB/line, 4 KiB/comment
and 32 KiB/complete output. Leading explicit comment delimiters are required;
quoted examples and trailing code comments are not instructions. Python source
uses tokenization to exclude multiline string literals. Missing/unreadable files,
symlinks, escaped paths and overflow fail without emitting partial context.

Both delivery cycles preserve the raw fetch/checkpoint in a root managed
document. `github.cli/pr_prepare_review_context` projects exact requests and
current PR state into a separate managed document, then merges that pre-gate
revision with the post-gate fetch. The cutoff filters only fresh conversation records;
pending pre-gate requests are retained and deduplicated by source/ID. Request
bodies and locations remain complete; bot replies/slash commands and duplicated
transport/diff bodies are omitted. The projection is capped at 64 KiB and
published atomically. Operator-feedback documents carry only the current bound
gate reason, avoiding duplicate PR bodies. Both root reviewer ledgers retain exact
decision identities and child scopes; only root initialization reads metadata.

The delivery runners require success, changes, rejection, validation failure,
retry/resume, independent same-ticket runs and actual fresh replay. They inspect
committed documents and real Git indexes. An installed failure is a blocker,
never a skip or a reduced passing matrix. Recovery fixtures withhold the initial
fetch and selected accepted-reply response, publicly cancel the owning synthetic
run, and recover only from the eligible canceled state in a fresh verified peer
scope. Actual client EOF and exact-source, complete native teardown are required.
Remote-marker reconciliation and GET-before-POST assertions still apply to both
reply surfaces. Separate full-graph checks require authored failure cleanup to
run once and prevent retry/resume from redispatching primary work afterward.
The two explanation reports and portable
projections can be regenerated without execution with
`scripts/record_delivery_explanations.py` and the same explicit runtime/plugins/base
arguments; outputs stay in fresh fixture storage for review.

All example test data is fictional. Private authored-copy tests must be run
separately and never bind operational inputs or read secrets.

### Automatic static checks and publication

`python3 -B scripts/check_static.py` is the sole automatic CI entrypoint. It parses
source as data and runs only static-analysis tools. No runtime, helper/test
execution, provider builds or plugin installation is allowed. Actions use verified
immutable commits; downloaded tool archives have exact checksums. CI requires no
sibling checkouts or operational credentials.

Use the published dependency tuple in [compatibility](../docs/compatibility.md)
for local runtime checks. The full command inventory and acceptance status live in
[validation](../docs/validation.md); archival results do not replace that gate.
Use [publication](../docs/publication.md) for the deterministic clean export and
separate exact-candidate approval checkpoint.
