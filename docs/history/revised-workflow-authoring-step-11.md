# Revised workflow authoring — Step 11

**Status: implemented; targeted macOS checks and independent review pass.** The
original plan ledger records one Step 11 commit per affected repository after
verification. Full Linux/macOS acceptance and unfiltered aggregate gates remain
Step 12.

## Identity and scope

| Component | Baseline on local `main` |
| --- | --- |
| Workflows | `590720eb60c7942d604aafcf87252ff6fb8e5e20` plus uncommitted Step 11 |
| Runtime | `4a60e8538a303e193c5650ac490d2ab2a6f11ca5` plus uncommitted skill/docs/tests only |
| Plugins | `7dedf8e1891d91e94e99ee8c5a3f3b3818697c3b`, clean/read-only |

Existing matching Step 10 debug binaries, both reporting `0.12.0`:

| Binary | SHA-256 |
| --- | --- |
| `transist` | `7f77e255101e16ba589a9aeaa3667c99ab6b1682d4d8b2aa408cd772f3cffea7` |
| `transist-admin` | `dd99dc9ca20f5bec126e3b8fb15514be009c92172ac7075368493da36f2dee5e` |

Validation uses macOS arm64 and the retained Step 9 Python 3.14.6 environment.
Public releases/pins stay `0.1.0`, schema IDs `v1`, runtime `0.12.0`. No signing,
private-key use, operational credentials/homes, real model/GitHub calls, plan/plugin
edits, source commits or push. Fresh standalone homes are explicitly fake-test
setup, not governed/live acceptance or implicit authoring installation.

## Fixtures and assistant records

The [finite fixture inventory](../../tests/fixtures/conversational_authoring/README.md)
is under `tests/fixtures/conversational_authoring`, separate from the four maintained
`EXAMPLES` roots. `scripts/check_authoring_fixtures.py` is the canonical required
runner. The default unfiltered installed-example runner calls its entire inventory;
selected maintained examples remain scoped. Missing prerequisites/scenarios fail,
never skip. Unit coverage proves both default inclusion and failure propagation.

| Fixture | Required scenarios / behavior |
| --- | --- |
| Diagnostic advisory | Approve sends exact diagnostic once and publishes managed response; reject or changed revision sends nothing |
| Approved draft publication | One model generation; exact reviewed draft consumed by real `github.cli/pr_create`; approve publishes once, reject/change publishes zero |
| Two-approval revision | Two distinct authored gates; first-only zero publication; both approve one; reject either/change yields zero |

Each fixture has portable sample inputs and contained inline prompts; the selected
OpenAI action does not declare a `prompt_file` binding. Model file input/output
and GitHub `body_file` use actual selected contracts. Installed real plugins,
compiler, sandbox, document storage, schemas and manual-gate CLI execute; only the
external model transport and `gh` peer are fake. One exact loopback listener is
declared and rebound identically for both revision definitions. No fabricated
plugin/action package or core/toy executor substitutes for compiled execution.

The base/revision use the same workflow identity, pins, prompts, sample bindings,
authority, limits and empty cleanup. Only a second gate and the protected read
reference change. YAML equality after undoing those edits and the actual CLI's
nine finite comparison paths guard this. Workflow/definition digests necessarily
change; no detached prompt/asset drift is hidden. Two approvals mean distinct
decisions, not a new distinct-person policy.

Each `walkthrough.md` is an actual implementing-assistant record using an explicit
**synthetic user brief**. The assistant loaded the checked-out skill/references,
captured intent, identified only missing bindings, inspected real schemas,
generated source, ran checks and reviewed actual explain/compare receipts. The
synthetic harness supplies fictional decisions/bindings, not fabricated human
replies or new operational permission. Fake-test approval is separate from real
publication/network/secret/policy/signing approval. Harness assertions do not by
themselves claim to prove model behavior; parent independently reviews the records.

## Current targeted receipts

Retained base: `projects/tmp/revised-authoring-step-11-validation/`.

| Command/check | Result / log |
| --- | --- |
| Dedicated installed runner, all three authoring fixtures only | 10 scenarios pass, zero skips; `installed-complete.log` |
| Fixture inventory/intended revision/port rebinding/prerequisite units | 5 pass; `fixture-units-final.log` |
| Installed runner default inventory + fail-closed integration units | 4 pass; `installed-inventory-units-final.log` |
| Runtime skill sequence/bindings/reference tests | 3 pass; `skill-units-final.log` |
| Runtime docs/skill validator | pass; `docs-skills.log` |
| Black/flake8, six changed Python paths | pass; `format-check-final.log`, `lint-final.log` |
| Markdown lint, 17 changed Markdown files | pass; `markdown-scoped.log` |
| Selected current-content privacy/path/link checks | pass; `selected-content.log` |

Each final fixture root retains source/plugin/binary provenance, payload
fingerprints, unbound/bound source/explanation reports, numbered CLI transcripts,
approval checkpoints, exact reviewed revisions/immutable blobs, peer observations,
settled runner IDs and `receipt.json` with `complete: true`. The revision also
retains `comparison.json`. Missing pre-install pins and required bindings are
explicit before start. Checks/explanation leave home bytes unchanged; deferred
payload checks remain deferred, secret values/external state remain unevaluated
statically. Workflow installation and execution happen only after authoring receipts.

The final execution matrix has ten root runs, eight model calls and two fake draft
publications. Pre-approval publication is zero. A successful post-review producer
creates a real new revision for every changed case; rejection/stale revision
prevents external consumption. Kernel attempt counts are distinct from actual
adapter calls. All owned runners/listeners settle before teardown.

Earlier failed attempts remain diagnostic: the first diagnostic assertion confused
attempts with external calls; the first revision comparison had an empty expected
path list; initial lint found two long lines. Those were corrected and refreshed
checks pass. `installed-final.log` is the preceding successful matrix; current
`installed-complete.log` includes the final checkpoint and bound-argument assertions.
An initial Markdown config expanded its requested changed-file list to 355 files
and hit two unrelated prompt-heading failures (`markdown-changed.log`). The final
command applies identical rules without global globs to the 17 changed files;
unrelated sources were not changed.

## Reproduce focused checks

From the workflow repository, set `PROJECTS` to its parent and use an existing
absolute disposable `VALIDATION` base. Retain stdout/stderr there. Prepend the
Python environment's `bin` to `PATH` for installed process children.

```sh
PYTHON="$PROJECTS/tmp/revised-authoring-step-9-validation/venv/bin/python3"
TRANSIST_BIN="$PROJECTS/transist-oss/target/debug/transist"
ADMIN_BIN="$PROJECTS/transist-oss/target/debug/transist-admin"
PLUGINS_DIR="$PROJECTS/transist-plugins"
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s tests -p test_conversational_authoring.py -v
env -u PYTHONPATH "$PYTHON" -B -m unittest discover -s tests -p test_check_installed_examples.py -v
env -u PYTHONPATH "$PYTHON" -B scripts/check_authoring_fixtures.py \
  --transist "$TRANSIST_BIN" --admin-bin "$ADMIN_BIN" \
  --plugins-dir "$PLUGINS_DIR" --fixture-base "$VALIDATION"
```

Optional repeatable `--fixture` selects a fixture; `--list` is inventory only.
The validation manifest records actual commands/exits/changed-file hashes. No full
publication gate, whole-repository tests, aggregate installed examples or
native Linux acceptance ran. Rollback reverts Step 11 sources while leaving the
runtime/migrated workflows usable; preserve immutable bundles/homes and never
overwrite an installed `0.1.0` payload.
