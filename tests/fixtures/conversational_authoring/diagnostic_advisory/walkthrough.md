# Assistant walkthrough: diagnostic advisory

## Synthetic user brief and decisions

Synthetic user brief used by the implementing assistant: “Read a fictional
diagnostic file, ask before sending it to a model, retain advice, never act on the
machine. One attempt; rejection stops.” This is a recorded authoring exercise,
not a transcript of a new human exchange.

The assistant loaded the repository-owned `transist-workflow-authoring/SKILL.md`
and references, identified stale workspace handoff advice, and updated the guide
before generating this fixture. Captured inputs: workspace, model, diagnostic
path. Output: managed advice. Systems/effects: bounded local read and one model
transfer after review; no publication or machine action. Repetition: none.

## Clarification analysis and contract inspection

Only missing bindings were the disposable workspace and local provider/model.
The authorized synthetic harness supplies these plus `diagnostics.txt`; there
was no missing behavioral decision and no reason to ask for document/temp paths.
No human answer or new permission is fabricated here.

Actual read-only catalog inspection used `shell/plugin.yaml`, its `read_file`
input schema and implementation, plus `openai.compatible/plugin.yaml` and
`chat_complete.input.schema.json` at the recorded plugin baseline. The model
action supports file input/output and inline `system_prompt`, not `prompt_file`.
It needs the declared secret binding. No missing integration was hidden in shell.

## Generated source and actual receipts

`workflow.yaml` declares bounded diagnostic/response documents, a read-only root
workspace, no root network, an exact loopback model step, one manual review and
its lexical `reviewed_by` read. Inline prompts and `inputs.example.yaml` are
portable; no cross-step workspace scratch or copied variables are generated.

The implementing assistant ran the actual dedicated runner and inspected its
CLI reports. Retained evidence base: `projects/tmp/revised-authoring-step-11-validation/`.
The final fixture root is identified in `installed-complete.log`; it contains
`source-check.json`, `explanation-unbound.json`, `explanation-bound.json`, numbered
command transcripts and `receipt.json`. The unbound explanation lists missing
workspace/model explicitly; the bound report resolves actual `0.1.0` contracts,
shows the gate/read, 64-KiB documents and opaque model prompt. Source validation
retains deferred materialized payload checks, not static success for future data.
Two bound explanations are byte-identical; checks/explanation leave home bytes
unchanged and create no run. This is a new definition, so no revision comparison.

## Execution boundary and observed assertions

Before fake execution, the assistant stated that source validation/explanation
does not establish real-provider readiness or consent. Real use still needs the
chosen workspace/provider/model, exact grants, credential binding and execution
approval. Only the user's existing **fake-test execution** authorization was used;
no real service permission, signing or private-key operation is claimed.

Actual compiled execution verifies zero model calls before approval; approval
sends exact captured UTF-8/CRLF/whitespace once and publishes a managed answer.
Rejection sends nothing. A successful writer publishing a new revision after
review blocks consumption with zero provider calls. Later workspace-byte changes
do not change the reviewed payload. The initial harness assertion incorrectly
equated kernel attempts with adapter calls; `diagnostic-attempt-1.log` is retained
as diagnosis. The final receipt distinguishes a failed kernel attempt from zero
external calls. These assertions are harness evidence; this authored record,
not an automated role log, documents what the assistant actually did.
