# Conversational authoring fixtures

Three synthetic authoring tasks, separately registered from the four maintained
`EXAMPLES` roots. Their canonical inventory and mandatory scenarios are in
`scripts/check_authoring_fixtures.py`. The unfiltered installed-example runner
also requires this whole inventory; no missing prerequisite is a skip. Use the
published `v0.1.0` runtime/plugins in [compatibility](../../../docs/compatibility.md).
Current public-candidate acceptance is in [validation](../../../docs/validation.md);
implementation walkthrough receipts remain historical.

| Fixture | Authored behavior | Required execution evidence |
| --- | --- | --- |
| [Diagnostic advisory](diagnostic_advisory/walkthrough.md) | Capture → review exact diagnostic → model → managed answer | Approve, reject, changed-after-review |
| [Approved draft publication](approved_draft_publication/walkthrough.md) | Capture brief → model draft → exact review → fake draft PR | Approve, reject, changed-after-review |
| [Two-approval revision](two_approval_revision/walkthrough.md) | Add a distinct second gate to the same draft definition | First-only has zero publication; both approve exactly one; reject either; changed revision blocks |

Prompts are contained inline in YAML. The selected native model action has no
`prompt_file` binding; `user_text_file` carries exact managed input bytes and
`response_file` publishes its result. `github.cli/pr_create` consumes `body_file`.
These are real `0.1.0` catalog actions, not fabricated plugin/test action packages.

Sample workspace paths are placeholders. The runner binds disposable canonical
read-only workspaces, an exact dynamic loopback port (source default `18765`) and
dummy-only model secret delivery. Fake `gh` sends its real plugin-generated
arguments to that same local observer; no GitHub connection, push or merge occurs.
The publication gate occurs after generation, not before the model call. All flows
are one-shot, with no retry/revision loop or authored cleanup; inspection retains
documents. Two gates require distinct decisions, not distinct-person enforcement.

Run from the workflow repository with an existing absolute disposable base:

```sh
python -B scripts/check_authoring_fixtures.py --transist "$TRANSIST_BIN" \
  --admin-bin "$ADMIN_BIN" --plugins-dir "$PLUGINS_DIR" --fixture-base "$VALIDATION"
```

Optional repeatable `--fixture` selects only named tasks; default requires all
three. `--list` is inventory only, never execution success. The runner source
validates unbound/bound definitions, explains twice, reports unresolved bindings
and missing installed pins before start, verifies resolved installed contracts,
and compares the revision against the base with identical inputs/pins. Expected
diff paths are finite in `revision-diff-paths.json`; YAML digests necessarily
change, but no prompt, pin, authority, condition, limit or cleanup drifts.

Each walkthrough is an actual assistant-authored record from implementation,
using a **synthetic user brief**, not a fabricated real-user exchange. It links
actual tool receipts and separates fake-test authorization from real execution.
The harness produces execution evidence, not independent proof of model behavior.
