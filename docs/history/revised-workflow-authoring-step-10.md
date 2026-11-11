# Revised workflow authoring — Step 10

**Status: both independent-review P2 corrections and refreshed targeted acceptance pass.**
The runtime identity, reply-publication and typed gate-decision prerequisites are
resolved in the coordinated working trees. Both source graphs and scoped units
pass. Both fresh complete default runners pass the corrected projection and
expanded recovery matrix with zero skips. Pre-review receipts remain retained as
history. Final independent review verified both corrections and the current
complete receipts. The original plan ledger records the three coordinated
source-repository commits after verification.

## Source and binary identity

| Component | Actual source |
| --- | --- |
| Workflows | `fdc5ec1fc7dfbd140c5c39fc479fb1777bdad6e3` plus this uncommitted migration on local `main` |
| Runtime/admin | `48b1d9aaf7b0f56d20eae73cd9068312dcae8771` plus the coordinated uncommitted typed `run.id` prerequisite |
| Plugins | `be895a6ca0cf406fba5d33b96485a67e2269f9c8` plus uncommitted reply and typed gate-contract/P2 repairs |

| Binary / selected identity | SHA-256 |
| --- | --- |
| Matching debug `transist` 0.12.0 | `7f77e255101e16ba589a9aeaa3667c99ab6b1682d4d8b2aa408cd772f3cffea7` |
| Matching debug `transist-admin` 0.12.0 | `dd99dc9ca20f5bec126e3b8fb15514be009c92172ac7075368493da36f2dee5e` |
| Runtime staging source, including typed metadata prerequisite | `951d797ab4e5ffca23c53817c3e6fa0148b191ecb3f3cceeed6432e7c7c77e8c` |
| Repaired GitHub `plugin.py` | `b9bd7a207d276a1fdf034af4ebbeb1e924c91cc8bca3b46e000d0acadab13d9d` |
| Runtime-locked repaired GitHub package | `22d0959e1c983e6d4867e06f04bd0cf0f3152662bb1c2cd7ccca4ce3ff4381e5` |

Current complete selected package fingerprints (directory path/mode/bytes digest),
byte/mode-compared against each fresh installation:

| Package | `plugin_dir_sha256` |
| --- | --- |
| `cursor.cli` | `ef218932dd7e4397948aec8de010e54622a6a964d41af9ddfd1da434275b3b6b` |
| `github.copilot.cli` | `461621a8fd129123890320e81c685a6ad4b7c1b123f8d93ae95f2287793d148d` |
| `openspec` | `2a4da3d515f6e1004c49e52c25b54ded0ead77b627ae37d95e8f5e9899dce57d` |
| `shell` | `02d55de908957ae2b98a14538974ec837a34229c6e23aa374257bf3620469269` |
| `git.cli` | `f7d2a2c780afc9ad4a1a94a06083c81b976a240e0497db8567b7571a9af8335c` |
| `jira.rest` | `e2679490f566fa1b270e03e2e89ea9c0743d6567a2894c54572a1f7491efc86d` |

The relevant fingerprints match the parent P2 handoff at
`projects/tmp/revised-authoring-step-10-gate-contract-validation/p2-payload-inventory.json`.
GitHub remains the unchanged reply-repair fingerprint above. Every fixture's
`source-provenance.json` records actual three-repository heads, dirty status,
working-diff hashes, complete selected file hashes and authored asset digests;
none is described as a clean committed Step 10 tuple.

All releases/pins remain `0.1.0`, schemas `v1`, runtime/admin `0.12.0`. Tests use
the pinned Step 9 Python 3.14.6 environment with `PYTHONPATH` unset. Native host is
macOS 15.7.7 arm64. No signing, operational-home replacement, real-provider call,
Linux execution, aggregate/final gate, plan edit, sibling edit, or source-repository
commit/push. Native Git commits are confined to the required synthetic targets.

## Implemented decisions

- Both roots declare managed issue, attachment tree, lossless bounded attachment
  projection, notes/summary, PR drafts/state, review context/checks/feedback and
  root reviewer ledgers. Cursor additionally declares plan/approved handoffs,
  validation/remediation state and reply-publication state. Mutable file readers
  use `update` with explicit literal initial content where required. Only intended
  source/OpenSpec deliverables remain workspace outputs.
- Root initialization reads strict typed metadata `run.id` before network work.
  No ticket/path/generated fallback exists. Children update the inherited ledger;
  root identity is never rebound to their IDs. Exact child gate identity, actor,
  timestamp, outcome, reason and reviewed-request metadata are retained with
  duplicate/conflict detection and 128-record/64-KiB bounds.
- Shared module input forwarding and one-output-copy variables are removed.
  Only stage-specific model data is passed explicitly. Action-bound profiles are
  recipe-local; root inputs remain lexically inherited. Repeated child invocations
  author fresh re-entry where needed; root documents carry current data.
- Git instruction scanning, approval readiness, merge readiness and review-context
  projection use Step 7 actions. Real Boolean outputs drive guards and publication
  resolution directly. Cursor retains primary and failed-validation override gates.
- Plan and implementation gates snapshot actual document revisions. Exact
  `reviewed_by` reads/export happen in the same lexical recipe; approved handoffs
  cross module boundaries as explicit documents. Workspace changes are not claimed
  covered by document approval. PR gates are documented control overrides, not
  grants to consume unapproved model context.
- Post-gate refreshes retain separate raw checkpoints and merge pending pre-cutoff
  requests. Completed cycles start a new projection. Cursor's remaining reply
  helper now performs data-only filtering/formatting; the plugin owns external
  publication and retry reconciliation. Legacy unmarked ambiguity is documented
  as operator reconciliation, never automatic repost.
- The legacy working-file guard remains before generation/commits, without requiring
  an unused exclusion for managed storage. Fixture workspaces have no operational
  exclusions, so misplaced files cannot be hidden by Git ignores. Source/OpenSpec
  are the finite allowed deliverables checked against native Git stages and disk.
- Parent PR loops require a successful child before reading its named exports.
  Exports do not exist while the child is blocked at a second gate; treating their
  absence as negative readiness would bypass pending validation-override decisions.
  The actual installed validation scenario exposed this authoring bug; a guard
  regression and the real two-gate path cover its correction.

## Installed validation and helper retirement

Actual maintained flow copies preserve every action/module/prompt/helper, changing
only fixture identity and root networking. Full selected real plugin payloads are
installed once in fresh homes and byte-compared with staging. External model CLIs,
Jira, GitHub and Git network peers are fake; local Git staging/commits are real.

The complete default inventory runs success, request changes, rejection, validation
failure, explicit retry/resume, independent same-ticket execution and actual replay.
Cursor additionally tests ambiguous legacy unmarked replies without another POST.
Partial diagnostic workers record `complete: false`; they cannot substitute for a
successful default invocation. Package bytes/modes and canonical directory digests
are compared to actual installed copies and recorded in every fixture receipt.

Extracted helper executables were retired only after real replacement paths passed.
Provider behavior coverage remains with the implementations, as required by Step 7:

| Retired behavior | Current coverage |
| --- | --- |
| Located instruction comments, literal exclusions, bounds, unsafe source/paths, deletion and timeout cases | `transist-plugins/plugins/git.cli/tests/test_instruction_comments.py`; real workflow scanner output reaches the fake model with tracked source location |
| Pending request projection, pre-cutoff retention, edits, deduplication, resolved threads, malformed/bounded/atomic publication | `transist-plugins/plugins/github.cli/tests/test_review_actions.py`; exact post-gate committed document revisions and actual model context in both installed flows |
| Latest-review identity, dismissal/supersession, typed approval/merge readiness, soft-fail versus operational failures | Step 7 GitHub action units/smokes and current installed flows; fake peers supply replaced/dismissed/anonymous reviews, and assertions inspect real managed approval outputs |
| File-based exit/Boolean bridge | Actual authored-control truth tables, missing/non-Boolean/current-verdict cases, blocked-child regression and real Boolean publication input assertions |
| Ticket-path retry counters and reviewer-ignore/path plumbing | Explicit managed counter units, root metadata/child-scope/duplicate/bounds units, real retry/resume/replay and no workspace operational exclusions |

Workflow-owned feedback, PR-format, relocation, actor/scope, malformed history,
deduplication and data-boundary tests remain local. The lower unit count after
retirement reflects provider tests already moved with their code, not required
skips or deletion of the corresponding behavioral acceptance. Remaining helpers
are contained staged-data assets; provider publication is never a shell helper.

Terminal rejection stops the recipe before a post-gate capture helper can run.
Its complete record remains in immutable runtime gate history, while the managed
model-context mirror retains decisions observed by subsequent steps. The fixtures
explicitly distinguish this boundary; they do not claim a rejected decision was
mirrored into a managed document. Runtime history plus the ongoing context mirror
retain every decision without inventing a post-stop append or changing rejection.

## Targeted checks and evidence

Retained base: `projects/tmp/revised-authoring-step-10-validation/`.

| Check | Current result / evidence |
| --- | --- |
| Both unbound/bound source checks | pass; `review-p2-source-final.log` |
| Full Cursor helper suite | 44 pass; `review-p2-cursor-units.log` |
| Full hotfix helper suite | 13 pass; `review-p2-hotfix-units.log` |
| Finite installed checker units | 4 pass, all four examples and all four publication-recovery combinations required; `review-p2-checker-units.log` |
| Delivery/profile authored wiring units | 6 pass; `review-p2-wiring-final.log` |
| Real CLI explanations twice + Step 9 portable projection | pass; `review-p2-explanations.log`; installed homes also retain full JSON/text |
| Installed hotfix | complete pass, 8 real roots, zero skips; `review-p2-installed-hotfix-final.log`, `hotfix_ticket_delivery-yv0pgdrw/` |
| Installed Cursor | complete pass, 11 real roots, zero skips; `review-p2-installed-cursor-final.log`, `cursor_ticket_delivery-mo1vndf6/` |
| Independent receipt/pin/namespace/process/recovery-event audit | pass; `review-p2-complete-delivery-audit.log/json` |
| Black check / flake8 | 27 changed Python paths pass; `format-check-final.log`, `lint-check-final.log` |
| Selected privacy/path/link checks | 60 changed current paths pass; `selected-content-final.log` |

Checked-in `explanation.snapshot.json` files fingerprint the generated definition
and portable text; they are not fabricated prose summaries. Full reports are in
`explain-hotfix_ticket_delivery-osww6u6n/` and
`explain-cursor_ticket_delivery-g0riohm3/`. Installed runners also explain twice and
require those fingerprints before invoking the full copied graph.

Each installed fixture retains numbered CLI transcripts, immutable run documents,
captured assets, per-file payload hashes, fake-provider observations and
`settled-runners.json`. Current runner code also records dirty source diffs/hashes,
authored asset/explanation fingerprints, endpoint counters and listener settlement.
All retained completed fixture runners exited. Earlier attempts are diagnosis,
not acceptance: source checks first caught profile/context lexical scope, and the
first fixture caught a terminal-state/runner-exit race. Current code waits for
actual runner exit before re-entry and cleanup.

The review-corrected complete homes executed 19 actual root runs in 15 real Git
workspaces, with 72 owned detached runners and 1,385 recorded loopback requests
(460 hotfix, 925 Cursor). Both
listeners settled and every owned runner exited. The managed mirrors retain
41 complete nonterminal decisions; the two terminal rejections remain in exact
immutable gate history. Every nonterminal mirror equals the corresponding complete
history records, including actor, timestamp, reason and reviewed revision scope.
The approval histories bind 76 exact document revisions (18 hotfix, 58 Cursor).
No successful root leaves a blocked contained child. Cases cover native source
staging/commits, request changes, both Cursor validation phases and override,
ambiguous accepted publication with both retry/resume, legacy unmarked fail-closed
behavior, independent same-ticket/same-workspace execution, replay and root cleanup.
No reduced or partial worker receipt substitutes for the default inventory.
`validation-inputs.json` records the finite changed-file hashes and Python paths.
Selected content validation models the one explicit unstaged helper move and
14 reviewed retirements; full publication/index validation remains separate.
No other missing candidate is skipped. Definitions have fingerprints
`4f1caa1af3abb2ab6af8d169ffdfe49e350445b06dcc7be0483eaacf87920ef2`
(hotfix) and `907bfbb684063fa6958742a32bcf59a2b64fe2510dc1dbfad1c2f03b8ad9eba7`
(Cursor), matching their checked-in generated snapshots and final installed receipts.

Commands from the workflows root, with explicit reviewed paths:

```sh
PROJECTS="$(dirname "$PWD")"
PYTHON="$PROJECTS/tmp/revised-authoring-step-9-validation/venv/bin/python3"
TRANSIST_BIN="$PROJECTS/transist-oss/target/debug/transist"
ADMIN_BIN="$PROJECTS/transist-oss/target/debug/transist-admin"
PLUGINS_DIR="$PROJECTS/transist-plugins"
VALIDATION="$PROJECTS/tmp/revised-authoring-step-10-validation"
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s examples/hotfix_ticket_delivery/tests -v
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s examples/cursor_ticket_delivery/tests -v
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s tests -p test_check_installed_examples.py -v
env -u PYTHONPATH "$PYTHON" -B scripts/check_examples.py --transist "$TRANSIST_BIN" \
  --plugins-dir "$PLUGINS_DIR" --home-base "$PWD/tmp" \
  --example hotfix_ticket_delivery --example cursor_ticket_delivery
env -u PYTHONPATH "$PYTHON" -B scripts/check_installed_examples.py --transist "$TRANSIST_BIN" \
  --admin-bin "$ADMIN_BIN" --plugins-dir "$PLUGINS_DIR" --fixture-base "$VALIDATION" \
  --example hotfix_ticket_delivery --example cursor_ticket_delivery
env -u PYTHONPATH "$PYTHON" -B scripts/record_delivery_explanations.py --transist "$TRANSIST_BIN" \
  --plugins-dir "$PLUGINS_DIR" --fixture-base "$VALIDATION"
env -u PYTHONPATH "$PYTHON" -B "$VALIDATION/validate_step10_changes.py"
env -u PYTHONPATH "$PYTHON" -B "$VALIDATION/audit_review_p2_delivery.py"
```

The retained finite-change validator runs Black `--check` and flake8
`--max-line-length 88 --extend-ignore E203,W503` on exactly its recorded Python
inventory, and applies the existing publication checker to current changed contents.
Six wiring tests were explicitly selected from `test_public_examples`:
validation/remediation limits, profile-bound budgets, delivery guards/scanner
actions, pending review merge, storage skill guidance and ticket/mutation declarations.

Prepend the pinned Python environment's `bin` to `PATH` for installed children.
The final installed commands were run separately for each selected delivery example
through retained `run_review_p2_installed.py` workers, preserving each actual checker
exit in `review-p2-complete-<example>-exit.json`. Both exits are zero and both mandatory
scenario receipts have `complete: true`. This avoids outer interactive-tool
deadlines without changing actions, schema validation or runtime execution. Do not
replace same-version payloads in a retained home.

Historical blockers are resolved: `reply-retry-blocker*.log/json` document the
pre-repair publisher; `root-metadata-blocker*.log/json` document the pre-repair
runtime file. Sibling Step 10 reports record their independent repairs. Neither
old diagnosis describes the current repaired metadata/publisher bytes.

Earlier failed/incomplete integration attempts are retained as history: an early
fixture waited for active work using a too-short settlement window; replay birth
is asynchronous; and the parent loop initially read absent exports while its
second child gate was waiting. The completed matrix covers the corrected paths.
An interrupted earlier Cursor changes root was canceled through the real CLI;
`cursor-interrupted-cancel.log` and `cursor-interrupted-settlement.log` retain
cleanup evidence. Partial diagnostic workers are explicitly incomplete and unused
for the final complete-runner acceptance claim.

## Review and rollback

The review-corrected acceptance receipt passes and is ready for renewed final review.
Parent owns one coordinated commit per affected repository after that review. Code
rollback selects the preceding immutable bundle/home; it does not rewrite newer
run records or undo external effects. Independent same-ticket documents are
isolated, but mutations of the same Git workspace still require coordination.
Native Linux and complete final acceptance remain Step 12.

## Independent full-review P2 corrections

1. The actionable-review filter previously dropped `diff_hunk_header`, because it
   only rebuilt a header from raw `diff_hunk` that Step 7 had already projected
   away. It now retains the exact schema-valid string header, checks its type and
   UTF-8 byte bound, and gives that existing projection precedence. Raw direct
   helper callers may derive only a header when none exists; full diff bodies
   never enter the actionable projection. A captured real Step 7 producer document
   is checked in under the Cursor test fixtures. Producer-to-consumer pure and CLI
   regressions cover absent/explicit-null numeric lines, all comments/IDs/bodies,
   exact PR context, invalid/oversized headers and raw fallback. Installed cases
   inspect both pre/post-gate managed revisions and the actual model prompt for
   the header when numeric lines are unavailable.
2. Conversation replies precede thread replies in the real response plan. The old
   retry/resume cases lost only the first POST, so they established conversation
   recovery, not accepted-thread/lost-response integration. Explicit fixture
   `loss_surface` selectors now require all four combinations in the full default
   inventory:

   | Case | CLI recovery | Accepted response lost on |
   | --- | --- | --- |
   | `retry` | `runs retry` | conversation |
   | `resume` | `runs resume` | conversation |
   | `retry_review_thread` | `runs retry` | review thread |
   | `resume_review_thread` | `runs resume` | review thread |

   Thread-loss cases first accept the conversation reply successfully, then accept
   the thread reply and lose its acknowledgment. Each receipt records the exact
   lost event, surface, endpoint, body, stable marker and remote ID. Real re-entry
   GET observations must fetch that exact marker on its existing surface and query
   both collections before any later POST. There must be no second POST for the
   lost marker. The real publisher's committed result must report
   `remote_duplicate_reply`; thread-loss batches must make no later reply POST at
   all because both replies already exist. The existing conversation cases remain
   mandatory. A finite-inventory unit prevents omission of either new thread case.

New review evidence uses `review-p2-*` filenames under the same retained base;
earlier failures and successful pre-review receipts remain historical evidence.
The captured Cursor helper change requires regenerated actual CLI explanations
and a new definition fingerprint; old same-version installs are never replaced.

Both complete default invocations and the refreshed audit exit zero. Each new
thread-loss case has one accepted thread POST, then real collection GETs returning
that exact stable marker and body, a committed `remote_duplicate_reply` response,
and zero reply POSTs after the lost acknowledgment. Conversation retry/resume still
reconcile their accepted conversation reply before posting the outstanding thread
reply. The explicit event/query records are retained in per-run observations,
mandatory scenario receipts and `review-p2-complete-delivery-audit.json`; the proof
does not rely on final post counts alone. All old failure logs remain retained,
including the pre-fix projection blob and review-P2 lint attempt.
