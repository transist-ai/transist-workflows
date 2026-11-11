# AI agent plugin canary

## Human request

The requested scope is six model integrations, checked in order with a fixed
small prompt. Keep CLI output/history bounded, preserve usage and subprocess
cleanup, and stop if any participant fails.

## Generated workflow explanation

The [explanation snapshot](explanation.txt) is a deterministic projection
of `workflows explain` JSON for the current `0.1.3` workflow. The installed
fixture regenerates it twice and requires exact bytes. Full raw JSON
retains platform-specific package/contract digests; the portable snapshot displays
authored order, limits, connections and authority without inferring prompt effects.
For the current workflow, with its exact plugins installed in an
explicit authoring home:

```sh
"$TRANSIST_BIN" workflows explain --path examples/ai_agent_plugins_canary/workflow.yaml \
  --home "$AUTHORING_HOME" --format json | \
  .venv/bin/python -B scripts/explanation_snapshot.py
```

## Expected result

CLI agent participants opt into compact output, invocation-only history, a
65536-byte context-file limit and a 98304-byte prompt limit. Ollama uses compact
output and its supported prompt limit, without CLI history or context-file
settings. Native provider calls retain their own action contract. This canary
does not scan source or create delivery working-file guards. Validate the
completed plugin schemas separately before treating authored graph checks as
installed-schema compatibility.

`ai_agent_plugins_canary@0.1.3` invokes six providers sequentially:
Copilot → OpenCode → Ollama → Cursor → Anthropic → OpenAI-compatible. Each is asked to return
`AI agent plugin canary: OK.` One action failure stops the workflow; later
providers are not tested. There are no retries or cleanup steps.

The workflow does **not** assert response equality. Inspect each action's
`response_text` and `canonical_response_text` where supplied with `runs show`.
A successful run alone does not prove the requested exact text was returned.

## Requirements and inputs

| Plugin | Pin | Execution prerequisites |
| --- | --- | --- |
| `github.copilot.cli` | `0.1.0` | Python, `gh`, `copilot`, the wrapper's `gh copilot` command surface, GitHub/Copilot authentication |
| `opencode.cli` | `0.1.0` | Python, OpenCode CLI, OpenRouter account/model access |
| `ollama.cli` | `0.1.1` | Its compiled Go adapter, Ollama CLI/server, an already-pulled local model |
| `cursor.cli` | `0.1.0` | Python, Cursor Agent CLI and existing login/model access |
| `anthropic` | `0.1.0` | Python, Anthropic Console API key, API billing and native model access |
| `openai.compatible` | `0.1.0` | Python, OpenRouter or OpenAI API account, model access and matching API key |

Obtain exact packages from the [public plugin repository](https://github.com/transist-ai/transist-plugins).
Manifests live under `plugins/<id>/plugin.yaml`. For actual installation, build
Ollama's adapter as documented by that package; Go is a build prerequisite, not
a workflow execution prerequisite. A consumer subscription is not Anthropic API
access. Provider CLI command surfaces and login lookup must be verified separately.

`inputs.example.yaml` supplies schema-valid placeholders, not runnable model IDs.
Replace all six model inputs with account-supported values, and set `repo_path`
to an existing canonical workspace. OpenCode uses `openrouter/<model-id>`;
Ollama needs an installed local tag. Timeouts must be positive integers;
Anthropic permits 1–120000 milliseconds. Ignore globs are not access enforcement.

Configure these logical references through the runtime secret provider:

| Logical reference | Plugin child binding |
| --- | --- |
| `OPENROUTER_KEY_PERSONAL` | `OPENROUTER_API_KEY` |
| `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| `OPENAI_COMPATIBLE_API_KEY` | `OPENAI_COMPATIBLE_API_KEY` |

The first reference is the public plugin's contract name, not a stored credential.
It cannot be renamed in this example without changing that plugin contract.
Supply values externally; never put them in inputs, assets or repository files.
The compatible-provider default is OpenRouter (`https://openrouter.ai/api/v1`).
For OpenAI directly, set `openai_compatible_base_url` to `https://api.openai.com/v1`
and choose a supported OpenAI Chat Completions model. Set
`OPENAI_COMPATIBLE_API_KEY` to the key for the selected provider. Both hosts are
allowed for the compatible step; other providers require a reviewed allowlist
change. The other OpenCode step continues to use OpenRouter.

## Authority and effects

The workspace is read-only. Cursor additionally requests writes beneath
`~/.cursor` for CLI state; this is an external host write, not a workspace write.
Governed policy grants authority separately. Do not grant the whole user home.
Invocation-private temporary/cache paths are owned by the plugins/runtime.

Root networking is denied. Each action requests an exact scope:

| Action | Endpoint scope |
| --- | --- |
| Copilot | `api.github.com`, `api.githubcopilot.com`, `github.com`:443, TLS |
| OpenCode | `openrouter.ai`:443, TLS |
| Ollama | `127.0.0.1`:11434, loopback HTTP |
| Cursor | `api2.cursor.sh`, `agentn.us.api5.cursor.sh`:443, TLS |
| Anthropic | `api.anthropic.com`:443, TLS |
| OpenAI-compatible | `openrouter.ai`, `api.openai.com`:443, TLS |

Redirects are disabled. These declarations are not proof of every endpoint a
current provider CLI needs. Review additional exact endpoints rather than grant
wildcards. Process-wrapper enforcement is not a complete OS egress guarantee;
the separately running Ollama server's traffic is outside the CLI scope.

Provider calls can transmit the prompt and agent-accessible workspace context,
incur charges and update external state. The fixed prompt and read-only workspace
do not eliminate those effects. `run://` response paths are action-local scratch,
not durable cross-step files; inspect persisted action outputs and promoted
artifacts instead. Nothing rolls back provider effects.

## Offline validation

Use the shared checker from the repository root with the pinned development
dependencies installed:

```sh
.venv/bin/python scripts/check_examples.py \
  --transist /absolute/path/to/transist \
  --plugins-dir /absolute/path/to/transist-plugins \
  --example ai_agent_plugins_canary --home-base "$PWD/tmp"
```

Create ignored `tmp` first if needed. The checker builds the real Ollama adapter
offline from complete reviewed Go source in disposable staging, installs exact
dependencies, and runs
unbound and representative-bound source checks. It strips credentials and
isolates the user home and Cursor state. It makes no provider calls and creates
no run. The fixture workspace contains synthetic text only.

Use the public `v0.1.0` [baseline](../../docs/compatibility.md); current acceptance
is recorded in [validation](../../docs/validation.md).
Historical source checks passed against the preceding development build. Publisher
signatures for Cursor 1.0.0 and canary 1.0.0 were verified, and the signed workflow
and its five dependencies installed in a separate governed evaluation home.
Installation created no run and does not prove readiness or invocation. Live
secrets, models, login sessions and provider availability remain untested.
These historical signatures do not validate current bytes. Source checks
and installed deterministic fixtures passed in the unfiltered
[historical Step 12 native matrix](../../docs/history/revised-workflow-authoring-step-12.md) against
the committed, unpushed local tuple. Both installed canary runs on each OS exercised
the then-existing five participants and checked responses, supported compact/history
budgets and usage (Ollama does not report tokens). The packages executed real
handlers, parsers and lifecycle code; external CLI executables and native Anthropic
HTTP were fake. Missing tooling or fixture prerequisites fail, never skip. This is not live-provider or governed
acceptance. They do not validate the current six-provider target or establish a new
test pass for current bytes. See [compatibility](../../docs/compatibility.md).

## Installation and deliberate execution

For standalone evaluation, install the exact dependencies into an explicit
standalone home, then install `workflow.yaml` with `workflows install --path`.
Review and enable process secret delivery only in that evaluation home. Check
installed readiness with the intended inputs before deciding to execute:

```sh
"$TRANSIST_BIN" workflows check ai_agent_plugins_canary@0.1.3 --live \
  --inputs-file /path/to/local-inputs.yaml --home "$RUN_HOME"
# After successful readiness and explicit review of all provider effects:
"$TRANSIST_BIN" workflows run ai_agent_plugins_canary@0.1.3 \
  --inputs-file /path/to/local-inputs.yaml --home "$RUN_HOME"
```

There is no manual gate in this canary; starting it dispatches provider work.
For governed delivery follow [governed use](../../docs/governed-use.md), keeping
signing keys outside runtime machines and using fresh versions for changed bytes.

## Cursor lifecycle and migration

The checked-in workflow pins `ollama.cli` at `0.1.1` and its other five plugins at
`0.1.0`. Action-bound profiles
select repeated prompt/lean settings from shared immutable context values. A
profile cannot select another action or widen authority; networks, logical secret
references and Cursor's exact state-write request remain on explicit steps. The
prompt, participants, order, inputs and authority of that five-provider revision
were unchanged by the profile change. Native Anthropic
keeps its `messages` contract and Ollama its supported generation contract; this
change introduces no cross-provider managed response-file fiction or batch action.
The plugin finishes its owned child processes and pipe readers
before returning its terminal result. The corrected runtime reports remaining
processes after that result as `protocol_error`, not an invocation timeout, and
retains validated, redacted terminal data in
`transist_process_lifecycle_evidence.json`. Increasing `cursor_timeout_ms` does
not repair a post-result teardown failure.

The current source uses `cursor.cli@0.1.0`; existing runs retain their pinned
dependencies and do not migrate when a package is changed. Publish and install
reviewed package bytes before creating a fresh run.
