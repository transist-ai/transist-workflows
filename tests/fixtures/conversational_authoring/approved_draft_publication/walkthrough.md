# Assistant walkthrough: approved draft publication

## Synthetic user brief and decisions

Synthetic user brief used by the implementing assistant: “Turn a fictional brief
into a concise draft PR description. Review the exact draft once before creating
one draft PR. Rejection stops. Do not push, merge or change code.” This is an
authoring exercise, not a fabricated real-user conversation.

The assistant loaded the checked-out workflow-authoring skill and references.
Captured goal/inputs: workspace brief, model, repository/title/head/base. Output:
managed draft and PR result. Systems/effects: local capture, model generation,
then publication only after review. Repetition: one shot; no cleanup mutations.

## Clarification analysis and contract inspection

Only runtime bindings were missing: disposable workspace/provider plus fictional
repository/title/head/base. The synthetic fixture decisions supply these in
`inputs.example.yaml`; no new human reply is claimed. No temporary path or ledger
ID question is needed. The desired publication system is explicitly GitHub, so
there is no missing integration decision to guess.

The assistant inspected real selected schemas for `shell/read_file`,
`openai.compatible/chat_complete` and `github.cli/pr_create`, including its
implementation: `body_file` accepts staged document data and preserves body text.
The actual action is in `github.cli@0.1.0`; it is not an invented publisher.
The fake replaces the external `gh` peer only, not APP, schema validation or the
plugin's file reading/command construction.

## Generated source and actual receipts

`workflow.yaml` captures the brief, generates a managed draft using supported file
input/output, then reviews and consumes the exact revision via `body_file`.
Root workspace is read-only; source networking is one exact loopback port.
Prompts are inline because the model action declares no `prompt_file` binding.
No broad shell action, cross-step scratch, loop, push, merge or workspace mutation
is authored. `inputs.example.yaml` carries portable fictional bindings.

The assistant ran actual source checks/explanations and inspected the reports:
the pre-install view explicitly reports unresolved pins; the installed view
resolves the real package digests. The final root in `installed-complete.log` retains
`source-check.json`, `explanation-unbound.json`, `explanation-bound.json`, command
transcripts and `receipt.json` under `projects/tmp/revised-authoring-step-11-validation/`.
Missing required bindings are explicit before start. Bound source checks defer
materialized document requests, leave external state/secret values unevaluated,
and write no home bytes/run. Repeated bound CLI JSON is byte-identical. No
comparison is needed for this new base; the revision walkthrough compares to it.

## Execution boundary and observed assertions

The assistant explicitly separated authoring from real publication permission.
Operational use still requires endpoint authority, authenticated `gh`, the model
secret/provider and an approved execution scope; a publication goal supplies none
of those approvals. Here the user authorized fake tests only. Fresh standalone
test homes install dependencies as explicit fixture setup; there is no implicit
operational installation, authorization, secret discovery or private-key use.

Actual compiled execution calls the fake model once to generate the reviewable
draft, makes zero publication calls while waiting, then approval permits exactly
one fake draft PR with the exact reviewed body and bound title/repository.
Rejection makes zero publications. A real successful writer creating a different
revision after approval blocks the consumer before `gh` publication. Model calls
are not incorrectly counted as publication calls. The assistant inspected the
successful first receipt (`draft-attempt-1.log`) and refreshed final receipts.
This walkthrough records assistant work; deterministic harness logs alone are
not asserted to prove model behavior.
