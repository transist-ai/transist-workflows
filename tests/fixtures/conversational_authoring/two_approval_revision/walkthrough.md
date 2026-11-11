# Assistant walkthrough: two-approval revision

## Synthetic user brief and decisions

Synthetic user brief used by the implementing assistant: “Revise the approved
draft-publication flow to require two separate approval decisions before the same
publication. Preserve its prompts, inputs, pins, network/workspace authority,
limits and one-shot behavior.” This is synthetic steering, not a new human reply.

The assistant loaded the repository-owned authoring skill and references and
captured the original goal, bindings, managed outputs, systems/effects and
rejection behavior from the base. Only the approval sequence changes. “Two” means
two distinct authored gates/decisions; no distinct-person identity policy was
requested or invented.

## Clarification analysis and contract inspection

No behavioral clarification is missing: rejection of either gate stops and both
review the same unchanged draft. The base sample bindings carry over byte-for-byte;
the harness supplies its disposable workspace/provider. No redundant binding or
storage question is asked. Actual `github.cli/pr_create` and OpenAI-compatible
file contracts were inspected as for the base, not replaced with guessed actions.

## Generated revision and actual comparison

The revision retains the base workflow ID and adds `review_publication` after
`review_draft`, with a distinct `gate_id`. The final `body_file` read names the
second lexical gate. All other YAML values match the base after removing that
gate and restoring the original read reference. Inline prompts remain identical;
there are no detached assets to change accidentally.

The assistant ran real source validation and `workflows explain --compare-to`
with identical bound inputs and installed pins, then directly reviewed
`comparison.json`. Its nine expected paths are checked in
`../revision-diff-paths.json`: three YAML/definition digest changes, graph edges,
step order, the protected binding's authored/bound/document projections, and the
new gate. There is no unrelated contract, action, authority, prompt or limit diff.
The first empty expected-path inventory intentionally failed and is retained in
`revision-attempt-1.log`; the actual comparison was inspected before recording
the finite expectation. `revision-attempt-2.log` records all four passing scenarios.

The refreshed final root named in `installed-complete.log` retains unbound/bound
source/explanation reports, exact comparison, command transcripts and execution
receipt under `projects/tmp/revised-authoring-step-11-validation/`. Missing
required inputs and pre-install contracts are explicit; installed exact pins
resolve. Explanation is deterministic and checks/explanation create no run or
home-byte changes. Deferred checks remain dispatch prerequisites.

## Execution boundary and observed assertions

The assistant presented the comparison and unresolved operational prerequisites
separately from fake-test execution. User permission covers deterministic local
peers only, not real publication/network/secret/policy/signing operations. A real
run would still need its own execution approval and both later gate decisions.

Actual runtime assertions require two distinct blocked gates reviewing the same
revision. First approval alone leaves **zero** publication calls and an unexecuted
publisher. Second approval permits **exactly one** publication. Rejecting either
gate yields zero publications. A successful writer after both approvals publishes
a new revision and blocks protected consumption with zero publication calls.
Fresh installed homes and real selected plugin payloads are used; no core/toy
executor or fabricated gate history bypasses these checks. This assistant-authored
record and actual CLI receipts are distinct from automated role-log claims.
