# Edge fault advisory

## Human request

“Read a diagnostic file from my workspace. Let me review the captured document
before sending those exact bytes to a model for at most three diagnostic checks.
Keep the answer as a managed document. Do not operate the machine.”

## Generated workflow explanation

The checked-in [explanation snapshot](explanation.txt) is a deterministic projection
of actual `workflows explain` JSON, generated with the
[current source tuple](../../docs/compatibility.md). Installed fixtures regenerate
it twice and require byte equality. The complete CLI report includes contract
digests and bindings; the portable projection omits platform-specific payload
digests. It is explanation, not validation, authorization or execution consent.

With the two exact plugins installed in an explicit authoring home, reproduce it:

```sh
"$TRANSIST_BIN" workflows explain --path examples/edge_fault_advisory/workflow.yaml \
  --home "$AUTHORING_HOME" --format json | \
  .venv/bin/python -B scripts/explanation_snapshot.py
```

## Expected result

`edge_fault_advisory@0.1.0` runs `shell/read_file` → manual document review →
`openai.compatible/chat_complete`. The workspace is read-only. `diagnostic_path`
defaults to `diagnostics.txt`; `workspace_path` and an account-supported `model`
are required. The bounded UTF-8 capture becomes the runtime-owned `diagnostic`
document. The gate records its exact revision ID and digest.

Approval permits one model call with that document as `user_text_file`, bound by
`reviewed_by: diagnostic_transfer`. The literal `system_prompt` gives the model
its technician-adviser role; this action does not support a first-class prompt
file binding. No duplicate diagnostic input, launcher pre-read, or manual byte
comparison is needed. Rejection sends no provider request. A newly published
revision requires fresh approval, even if its bytes are identical. Later changes
to the original workspace file do not change the captured document. Review does
not approve arbitrary workspace mutations.

The answer is published as managed `response`, outside the workspace. Both
documents are limited to 65536 bytes; the provider prompt budget is 98304 bytes,
`max_completion_tokens` is 512 and the timeout is 30000 ms. Select a provider/model
supporting that field and the patched OpenAI-compatible schema; the preceding
published `0.1.0` plugin rejects it. Equal versions do not prove equal payloads;
use an isolated evaluation home, not an in-place change beneath pinned runs.
A provider/publication failure
remains a failed run. There is no revision loop or automatic approval.

## Validation and deliberate execution

Requirements: the verified public Transist 0.1.1 binary, Python 3.11 with the pinned
dependencies, and `shell@0.1.0` / `openai.compatible@0.1.0` manifests from the
matching plugin checkout. Supply credentials externally through the runtime
secret provider, never through inputs, prompt text or documents.

The launcher defaults to **source validation only**, using a fresh retained
standalone home under ignored `tmp/`. It installs the two dependencies and enables
process secret-delivery metadata only there; it creates no run and requires no
credential. It selects the workspace/file without opening diagnostic contents:

```sh
.venv/bin/python -B examples/edge_fault_advisory/run_local.py \
  --transist "$TRANSIST_BIN" --model YOUR_OPENROUTER_MODEL_ID \
  --shell-manifest "$PLUGINS_DIR/plugins/shell/plugin.yaml" \
  --openai-manifest "$PLUGINS_DIR/plugins/openai.compatible/plugin.yaml" \
  --workspace /absolute/workspace --diagnostic-path diagnostics.txt
```

**Execution approval is separate:** only after reviewing the definition, inputs
and requested effects, repeat with `--execute`. This explicitly selects local
capture/start, installs the workflow source, and requires live readiness including
`OPENAI_COMPATIBLE_API_KEY`. Declared document payload checks defer to dispatch;
failed authority, secrets and prerequisites still block. The launcher prints the
retained home and stops at the gate; it never records a gate decision.

Review `runs show RUN_ID` in the printed home. The blocked summary and TUI show
the runtime-owned diagnostic revision, digest, size and content link. With the
companion inspection server attached to the same home, its Gates view opens the
exact document content. Then make a deliberate decision:

```sh
"$TRANSIST_BIN" --home "$RUN_HOME" runs show RUN_ID
"$TRANSIST_BIN" --home "$RUN_HOME" runs gate approve RUN_ID diagnostic-transfer \
  --actor YOUR_NAME --reason REVIEWED_DOCUMENT
# Or: runs gate reject RUN_ID diagnostic-transfer --actor YOUR_NAME --reason REJECTED
"$TRANSIST_BIN" --home "$RUN_HOME" runs show RUN_ID --format json
```

Approval resumes execution and needs the externally supplied key. Final JSON
contains the provider's `response_text` and usage. The committed execution record
`<RUN_HOME>/runs/run_RUN_ID/step_executions/advise/execution_001.json` records
`document_revisions`; select the entry whose `document` is `response` and use its
`revision_id`. Inspect that immutable response through
`GET /api/v1/runs/RUN_ID/documents/REVISION_ID/content` on the companion server.
This is a managed-document route, not a workspace-file path or expired staging
file. Preserve the runtime home while its evidence is needed.

## Authority and offline fixtures

Root networking is denied. Only `advise` requests TLS to `openrouter.ai:443`, with
no redirects; the destination and logical secret reference remain explicit and
literal. A provider change requires reviewing both `base_url` and its exact
allowlist. Process egress declarations are not a complete OS network guarantee.
Model output is untrusted advice; it authorizes no device action.

The [selected source and installed checks](../../scripts/README.md) use fictional
data and local fake transports only. They cover approval, rejection, waiting
restart and genuine publication of a new revision after approval, and assert
exact provider bytes and zero external calls before approval. They use no real
provider credential. [Governed use](../../docs/governed-use.md) separately requires
reviewed packaging, fresh signatures, imported trust, authorization and readiness.
Historical packages remain immutable rollback material, not signatures for this
revised source.

[Historical Step 12 acceptance](../../docs/history/revised-workflow-authoring-step-12.md) includes
all four advisory roots in the unfiltered matrix on native Linux arm64 and Apple
Silicon macOS. The accepted source tuple is committed locally and unpushed;
fake-provider acceptance does not establish public fetchability, authenticated
live execution or governed publisher distribution.
