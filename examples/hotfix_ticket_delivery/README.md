# Hotfix ticket delivery

## Human request

“Implement this Jira ticket in my selected repository. Let me review implementation
revisions, then use explicit Git/GitHub steps to commit, push, review and merge.”

## Deterministic explanation and expected result

`hotfix_ticket_delivery@0.1.0` fetches the issue and an attachment tree, implements
the fix with Copilot, waits at implementation review, commits/pushes, drafts an
ordinary PR, and runs bounded PR review/remediation before squash merge and Jira
completion. It does not generate an OpenSpec plan or claim automated validation
of the implementation. Dedicated actions own commits, publication and cleanup.

Generate the explanation from the exact reviewed source and installed contracts:
set `EXPLANATION_JSON` to a file outside this package.

```sh
"$TRANSIST_BIN" workflows explain --path workflow.yaml --format json \
  --home "$AUTHORING_HOME" > "$EXPLANATION_JSON"
"$PYTHON" ../../scripts/explanation_snapshot.py < "$EXPLANATION_JSON"
```

The [historical Step 10 evidence](../../docs/history/revised-workflow-authoring-step-10.md) records
two identical actual CLI reports and their portable Step 9 projection. Full JSON
includes nested module steps, gates, bounds, authority and asset/contract digests.
[The generated snapshot](explanation.snapshot.json) fingerprints the definition
and portable text; the full JSON/text stay in retained validation evidence.
Prompts and scripts remain opaque external behavior. An explanation is neither
readiness nor permission to execute.

Expected result after approved execution: intended source changes committed to a
feature branch, an AI-assisted non-draft PR, explicit PR review decisions or typed
approval/mergeability checks, squash merge, Jira completion, and retained runtime
history/documents. Rejection stops the run. Authored cleanup runs automatically on
success or failure. PR-based trunk synchronization runs only after successful
delivery; early failure cleanup never reads an unpublished PR document. Both
outcomes check out trunk and remove the local feature branch. `runs cleanup`
recovers unfinished or failed cleanup; inspect saved state before using it.

## Prerequisites and authority

- Public Transist `0.1.1` with typed `run.id` metadata;
  all workflow/module releases and exact plugin pins are `0.1.0`, schemas `v1`.
- Real selected `git.cli`, `github.cli`, `github.copilot.cli`, `jira.rest` and
  `shell` packages. The GitHub package must include publication reconciliation;
  gate-aware contracts must accept the runtime's exact reviewed decision shape.
- Python 3, Bash, Git, authenticated `gh`/Copilot, target-repository build/test tools,
  and credentials permitting the declared Jira/GitHub effects.
- `JIRA_AUTH_HEADER` is a runtime secret reference, never an input or persisted file.
  Copy `inputs.example.yaml` outside the package; set the actual repository, ticket,
  Jira URL, branch/trunk, statuses, models and approval count.
- Edit the root's exact fictional Jira host allowlist **before** packaging or
  installation. Root authority is inherited by modules: full access to the exact
  selected workspace, declared GitHub/Copilot/Jira HTTPS hosts and port 443. A
  declaration requests authority; governed policy must grant it separately.

Install reviewed dependencies into a fresh authoring home, then check unbound and
with representative inputs. For governed delivery follow [governed use](../../docs/governed-use.md):
package/sign administratively, install, check readiness, review exact authority,
authorize if appropriate, then recheck readiness. Installation creates no run and
grants no authority. Obtain execution approval separately before `workflows run`.
Every real manual gate still needs an explicit actor and reason.

## Managed documents and review boundaries

All ticket payloads, attachment bytes, projected attachment context, model notes,
summary/PR drafts, PR/check results, pending review requests, feedback and the
reviewer ledger are root-declared managed documents **outside Git**. Process
actions receive invocation-private staged paths. A successful invocation publishes
its document batch atomically; failure/cancellation leaves committed heads intact.
Resume retains revisions. Replay initializes a fresh namespace and root identity.

The root initializer reads its own runtime metadata `run.id` exactly once before
network effects. Children update the inherited ledger; their own invocation IDs
remain in individual decision scopes and never replace the root header. There is
no caller-generated ledger identity or storage prefix. Missing/malformed metadata
fails closed. Exact actor, reason, timestamp, decision identity and reviewed scope
are retained, bounded to 128 decisions and 64 KiB; overflow fails without truncation.
The ledger is model context, not authority. Terminal rejected decisions remain in
the runtime's immutable gate history; no post-rejection model work runs.

The first implementation pass receives empty inline-comment context and does not
scan the repository for `tst:` markers. After implementation review requests
changes, the workflow scans the reviewed working tree and publishes complete
inline-comment context for the next implementation pass. Approval exits without
scanning; rejection stops without further model or scanner work. Each pass has a
fresh child identity and inherits the published reviewer ledger and comments.
The `max_iters: 5` and 16-hour bounds are unchanged. An explicit approval check
after the loop prevents exhaustion from advancing to commit or PR creation.

Implementation review snapshots notes, summary and PR-body revisions. A local
export step reads those exact revisions with `reviewed_by: review_implementation`
and publishes explicit root-shared handoff documents. Parent/child gates are not
treated as lexically interchangeable. A new model revision needs a new review.
Reviewing these documents does not snapshot or approve arbitrary workspace bytes.

The PR review gate reviews the exact pending requests, PR and check evidence. It
is an intentional control override: approve exits despite unmet automatic checks;
request changes refreshes and remediates; reject stops. Request changes is not an
approved-document read grant. Post-gate projection merges pending pre-cutoff
requests with the fresh fetch rather than replacing them. Completed cycles start
new projections, preserving old evidence as immutable revisions.

Attachment trees retain relative manifests and exact bytes. Because the model
actions accept files, a bounded, lossless base64 projection supplies manifest and
member bytes as context; over 64 KiB fails before the model call. The original
10 MiB/100-file tree remains inspectable. No staged path is saved in a manifest.

## Workspace and recovery

Only intentional source changes belong in the target repository. No ignore rule
is needed for managed documents. The pre-generation/pre-commit guard still rejects
stageable legacy `.transist`/interaction files; it never edits exclusions. Agent
steps must not copy operational data into the workspace or commit/push themselves.

Two independent runs of the same ticket have isolated documents, **but mutations
of the same Git workspace still require coordination**. Managed documents do not
rollback Git mutations or external Jira/GitHub effects. Retry uses the frozen
recipe/assets; source fixes require fresh validated bytes and a fresh run.

Use `runs show`, `runs preflight` and `runs tail` before retry/resume, and inspect
exact document revisions through the runtime inspection surfaces. Preserve old
immutable installations for rollback; never replace same-version payloads.

## Targeted offline validation

For focused lifecycle execution coverage with synthetic model/scanner actions,
run the explicit fixture runner below. It uses fresh standalone homes under the
catalog's existing `tmp` directory, the real shell plugin, real gates and exact
document-review checks; it never executes the installed operational workflow.

```sh
"$PYTHON" -B tests/run_runtime_regressions.py \
  --transist "$TRANSIST_BIN" --shell-plugin "$SHELL_PLUGIN_PACKAGE" \
  --fixture-base "$FIXTURE_BASE"
```

```sh
"$PYTHON" -B -m unittest discover -s tests -v
"$PYTHON" -B ../../scripts/check_examples.py --transist "$TRANSIST_BIN" \
  --plugins-dir "$PLUGINS_DIR" --home-base "$SOURCE_CHECK_BASE" \
  --example hotfix_ticket_delivery
"$PYTHON" -B ../../scripts/check_installed_examples.py --transist "$TRANSIST_BIN" \
  --admin-bin "$ADMIN_BIN" --plugins-dir "$PLUGINS_DIR" \
  --fixture-base "$FIXTURE_BASE" --example hotfix_ticket_delivery
```

Source checker storage must use its documented approved base; see
[validation tooling](../../scripts/README.md). Installed fixtures use complete real
packages and actual workflow graphs with deterministic fake peers. The unfiltered
[historical Step 12 matrix](../../docs/history/revised-workflow-authoring-step-12.md) passed all eight
hotfix roots on both native Linux arm64 and Apple Silicon macOS. Accepted local
commits are unpushed; these checks imply neither public fetchability nor
authenticated real-provider execution or governed publisher distribution.
