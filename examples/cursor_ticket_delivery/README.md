# Cursor ticket delivery

## Human request

“Turn this Jira ticket into a reviewed OpenSpec plan and implementation in my
selected repository. Validate it, deliver a draft PR, and retain my review scope
through remediation, retry and PR review before an explicitly governed merge.”

## Deterministic explanation and expected result

`cursor_ticket_delivery@0.1.0` fetches Jira/attachments, prepares and reviews an
OpenSpec plan, implements and reviews changes, verifies alignment, remediates
failed validation within bounds, and delivers a draft PR. Dedicated Git/GitHub
actions own staging, commits, push, replies, awareness comments and squash merge.
Set `EXPLANATION_JSON` to an output file outside this package.

```sh
"$TRANSIST_BIN" workflows explain --path workflow.yaml --format json \
  --home "$AUTHORING_HOME" > "$EXPLANATION_JSON"
"$PYTHON" ../../scripts/explanation_snapshot.py < "$EXPLANATION_JSON"
```

The [historical Step 10 evidence](../../docs/history/revised-workflow-authoring-step-10.md) records
two identical actual CLI reports and their portable Step 9 projection. Full JSON
shows every nested action, gate, document connection, loop bound, authority request
and pinned asset/contract digest. Model prompts and scripts remain opaque behavior;
the explanation neither proves readiness nor authorizes execution.
[The generated snapshot](explanation.snapshot.json) fingerprints the definition
and portable text; retained evidence contains both full reports and the projection.

Expected approved result: reviewed source and `openspec/changes/` deliverables,
commits on the feature branch, a labeled draft PR, exact per-comment outcomes,
typed approval/mergeability evidence, validation or explicit overrides, squash
merge and Jira completion. Rejection stops. Authored root cleanup runs automatically
on success or failure. PR-based trunk synchronization is success-only, so early
failure cleanup never reads an unpublished PR document. Both outcomes check out
trunk and remove the local feature branch. `runs cleanup` recovers unfinished or
failed cleanup; inspect retained state before cleanup, retry or resume.

## Prerequisites, readiness, authority, execution

- Use public Transist `0.1.1` with the typed `run.id` metadata field.
  Workflow/module/plugin releases remain `0.1.0`; format identifiers remain `v1`.
- Install exact real `cursor.cli`, `git.cli`, `github.cli`, `jira.rest`, `openspec`
  and `shell` packages into a fresh home. Gate-aware contracts must accept the
  runtime's reviewed decision shape. The GitHub package needs the Step 10 stable
  reply-marker reconciliation repair, including complete bounded reads.
- Python 3, Bash, Git, `gh`, Cursor Agent (`cursor-agent`), `openspec`, authenticated
  provider/GitHub sessions, target build/test tools, and an initialized target
  `openspec/` directory are prerequisites. The workflow does not initialize it.
- Configure `JIRA_AUTH_HEADER` as a runtime secret. Keep credentials out of all
  inputs, documents, prompts and repository files. Copy `inputs.example.yaml`
  outside the package and set the actual repository, ticket, Jira URL, statuses,
  branch/trunk, approval threshold and supported stage-specific model IDs.
  The current Cursor package accepts but ignores its compatibility tool-list and
  reasoning-effort fields; workflow conventions do not narrow full workspace authority.
  An operator/reviewer must make the draft ready in GitHub before merge. A
  Transist override does not make a GitHub draft mergeable.
- Before signing/installing, edit the root's exact fictional Jira host allowlist.
  Modules inherit the root ceiling; they do not repeat or widen network/workspace
  authority. Root requests full access to the exact workspace, declared HTTPS/443
  endpoints and Cursor state writes under `~/.cursor`.

First validate authored source with installed contracts and representative inputs.
Then follow [governed use](../../docs/governed-use.md) for administrative packaging,
installation, readiness and exact authorization. Declarations request authority;
policy grants it. Installation creates no run. Fix non-policy prerequisites before
authorization. After readiness passes, obtain execution approval separately before
`workflows run`. Real manual gates require an explicit actor and reason.

## Managed storage and lexical reviews

Ticket JSON, attachment trees, attachment context, plan/review context, model notes,
PR drafts/results, validation reports, remediation bookkeeping, reply state and
reviewer ledgers are root-declared managed documents outside the Git workspace.
Each process action receives private staged copies; successful batches publish
atomically. Failed/canceled actions cannot advance committed heads. Resume keeps
revisions; replay creates a fresh namespace and reruns producers.

The root initializes reviewer context from its own exact metadata `run.id` before
network effects. It never parses a path/ticket, invents an ID, or asks the caller
for one. Children inherit that same ledger; their own IDs distinguish individual
gate scopes. Full reason/actor/timestamp/outcome and reviewed-request metadata are
retained, with exact duplicate detection and 128-decision/64-KiB limits. Exceeding
either bound fails rather than dropping history. The ledger is context, not new
authority or proof of passing tests. A terminal rejection stays in immutable
runtime gate history; execution stops before any subsequent model work.

Plan review snapshots plan and OpenSpec metadata revisions. Local `reviewed_by`
reads enforce that exact approval while exporting root-shared approved handoffs
and copying the approved plan into `openspec/changes/<ticket-slug>/plan.md`.
The first implementation pass uses empty inline-comment context, without scanning
for `tst:` markers. Only a subsequent implementation-review request for changes
triggers a scan, publishing comment context for the next fresh iteration. Approval
exports the exact reviewed documents without scanning; rejection stops. The
`max_iters: 5` and 16-hour limits remain unchanged, with an explicit post-loop
approval check before downstream validation, commits or PR creation. Stage-specific
models and the prior reviewer ledger remain available across fresh iterations.
PR-review scans remain after PR creation and the request to remediate its review.

Implementation review similarly snapshots notes, summary and PR body before a
local reviewed export. Those bindings name gates in the **same recipe**; a parent
gate is never pretended visible to a child. A changed revision needs reapproval.
Document review does not snapshot arbitrary Git workspace mutations.

PR review gates are explicit control decisions, with exact evidence revisions:

- Automatic exit requires an open PR, typed approval/merge readiness and current
  Boolean OpenSpec verification. Already-merged PR handling remains explicit.
- The primary gate may override unmet automated checks. Request changes refreshes
  comments/PR state and runs remediation; it is not an approved-document grant.
- If approval/merge checks pass but OpenSpec fails, an awareness comment is upserted.
  Exiting despite the mismatch requires the additional validation-override gate.
  Its request-changes decision vetoes initial approval and starts remediation.
- Post-gate fetches merge pending pre-cutoff requests rather than losing them.
  Completed cycles start a new projection; prior revisions remain inspectable.

Stage-specific models are ordinary module inputs only where needed. Other inputs
are lexically inherited. Repeated invocations use fresh children where authored;
documents remain root-shared and use current action arguments, not stale child
path inputs. Action-bound profiles stay recipe-local, with supported compact
output, invocation history and explicit 64-KiB context/96-KiB prompt budgets.

Attachment trees preserve exact bytes and relative manifests (10 MiB/100 files).
File-only model contracts receive a lossless base64 projection of manifest and
members. Projection over 64 KiB fails before a provider call; the original tree
stays inspectable. Invocation paths are never stored in the manifest.

## Publication, Git isolation and recovery

Only source changes and `openspec/changes/` are workspace deliverables. Managed
operational files need no Git exclusions. A read-only guard still refuses
stageable legacy operational/interaction files before generation and each
`add_all` commit, without editing ignore rules. Model steps must not create
commits, push or copy operational context into the repository.

Explicit reply outcomes cover every actionable comment. Clarification/rejection
replies are formatted locally and published through `github.cli`. Thread resolution
requires all its comments addressed **and** a real committed change; the direct
Boolean commit result controls that plugin input.

After ambiguous publication failure, retry/resume re-enters the real publisher.
It inspects complete bounded conversation and review-comment collections before
any repost, reconciles exact stable markers/body/target, and fails on incomplete
or conflicting evidence. Legacy unmarked identical replies are ambiguous: stop
for operator reconciliation, inspect remote history and retained run evidence,
and do not automatically repost or delete markers/state to force progress.

Independent runs of the same ticket have isolated documents. **Mutations of the
same Git workspace still require coordination.** Local revisions cannot rollback
Git changes or Jira/GitHub effects. Retry/resume retains frozen recipe/assets;
source fixes require a new validated package and fresh run. Preserve immutable
prior installations for rollback and never replace same-version payloads.

## Targeted offline checks

Focused lifecycle execution uses copied implementation graphs, a real local
runtime and shell plugin, and synthetic model/scanner actions. It verifies first
approval, request-changes feedback across fresh children, rejection and early
failure cleanup without contacting providers or launching the installed workflow:

```sh
"$PYTHON" -B ../hotfix_ticket_delivery/tests/run_runtime_regressions.py \
  --transist "$TRANSIST_BIN" --shell-plugin "$SHELL_PLUGIN_PACKAGE" \
  --fixture-base "$FIXTURE_BASE" --example cursor_ticket_delivery \
  --case approve --case request-changes --case reject --case early-failure
```

```sh
"$PYTHON" -B -m unittest discover -s tests -v
"$PYTHON" -B ../../scripts/check_examples.py --transist "$TRANSIST_BIN" \
  --plugins-dir "$PLUGINS_DIR" --home-base "$SOURCE_CHECK_BASE" \
  --example cursor_ticket_delivery
"$PYTHON" -B ../../scripts/check_installed_examples.py --transist "$TRANSIST_BIN" \
  --admin-bin "$ADMIN_BIN" --plugins-dir "$PLUGINS_DIR" \
  --fixture-base "$FIXTURE_BASE" --example cursor_ticket_delivery
```

See [validation tooling](../../scripts/README.md) for approved storage locations
and finite runner inventories. Fixtures retain real complete plugin payloads,
captured source assets and full workflow graphs; only external peers are fake.
The historical unfiltered [Step 12 matrix](../../docs/history/revised-workflow-authoring-step-12.md)
passes on native Linux arm64 and Apple Silicon macOS, including all 11 Cursor
roots and all four conversation/thread lost-response retry/resume cases without
duplicate posts. The accepted local commits are unpushed. Fake-peer evidence does
not establish public fetchability, authenticated real-provider execution or
governed publisher distribution.
