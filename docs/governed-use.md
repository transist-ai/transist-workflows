# Governed use

These examples ship unsigned source. A standalone home is appropriate for
explicit local evaluation; it is not a substitute for governed policy or trust.
Never put credentials, signing keys or operational inputs in an example package.

## Prepare source

Read the example's README and customize its inputs and exact endpoint allowlists.
Ticket-delivery examples use a fictional Jira host; editing `jira_site_url` alone
does not update the authored allowlist. Check every affected module before
signing. Review workspace writes, external transfers and branch cleanup.

### Review delivery storage before launch

Ticket-delivery operational data uses root managed documents outside the Git
workspace: ticket/attachment content, plan/notes, review context, PR drafts,
retry bookkeeping and reviewer ledgers. Runtime staging supplies private process
paths; success publishes immutable revisions atomically. Resume retains heads;
replay creates a fresh namespace and metadata-derived root identity. Keep secrets
out of every persisted document and workspace file. `run://` remains invocation
scratch and must not replace managed cross-step storage.

No Git exclusion is required for managed documents. Guards still reject stageable
legacy operational/interaction files before generation and every all-changes
commit; they never edit the target's ignore rules. Intentional source changes and
Cursor's `openspec/changes/` bundles remain reviewable repository deliverables.
Document approval binds exact revisions in its own lexical recipe, not arbitrary
workspace bytes. Independent same-ticket documents are isolated; **mutations of
the same Git workspace still require coordination**. Runtime documents cannot
reverse Git mutations or external Jira/GitHub effects.

### Authoring bindings

- Declare bounded root documents as `kind: file` or `kind: tree`; trees also
  require `max_files`. Modules inherit names without forwarding staged paths.
- Bind `{$document: name, access: read}` (or `access: write` / `access: update`)
  only at path-valued inputs supported by **process** actions.
  `read` stages the committed revision read-only;
  `write` supplies an absent output path; `update` stages current bytes writable.
  Read/update require a published head or a literal file `initial` value. These
  bindings are not supported by HTTP/MCP actions.
- Use typed `steps.<id>.out.<field>` values and declared module outputs for
  control/dataflow, not files containing exit codes or Boolean strings. Read child
  exports only after that child succeeds; a blocked child has not completed them.
- For a protected read, `reviewed_by` names the exact manual-gate **step ID** in
  the same lexical recipe, not its `gate_id` or a parent/sibling gate. Approval
  binds revision ID and digest; even identical bytes in a new revision require
  review. Export approved handoffs explicitly inside that scope.

See the runtime's
[workflow schema](https://github.com/transist-ai/transist/blob/v0.1.0/docs/public/reference/workflow-schema.md)
for the complete contract. Operational intermediates stay in managed documents;
source and OpenSpec deliverables stay in Git. Never add ignore rules as a storage
workaround.

Workflow and module releases advance independently; plugin pins name exact SemVer
releases. Schemas remain `transist.flow.v1` and `transist.module.v1`. Historical
checks and signatures do not validate changed bytes. Repeat affected checks against
the selected plugin schemas and complete reviewed packaging before governed use.
Use fresh disposable homes for validation. Never replace published same-version
payloads; preserve previous homes/packages for rollback.

[Historical Step 12 acceptance](history/revised-workflow-authoring-step-12.md) covers real
installed packages with fake peers on native Linux and macOS. The accepted local
commits are unpushed; that evidence establishes neither public availability nor
authenticated live execution or governed publisher distribution.

```sh
"$TRANSIST_BIN" workflows check --path /path/to/example/workflow.yaml --home "$TRANSIST_HOME"
```

Install the exact plugins separately and repeat source checking with
representative non-secret inputs. A source check creates no run and does not
dispatch a provider. Assign a distinct version when executable bytes change.

## Package outside the runtime

An authorized administrator packages reviewed source on the signing machine. The
version below is an example; use the selected workflow's actual version throughout:

```sh
transist-admin workflow package /path/to/example/workflow.yaml \
  --version 0.1.0 \
  --private-key-file /path/to/administrator-key \
  --output /path/to/new-package
```

This operation uses a private key. Keep that key off runtime machines. Obtain
signed plugin packages and the approving public trust roots separately. Import
only reviewed public roots; none are supplied by this repository.

## Install, check, authorize, then execute

Keep the local JSON inputs file outside the signed package; use the example's
input keys with reviewed operational values and no credentials.

```sh
"$TRANSIST_BIN" workflows install --package /path/to/new-package --home "$TRANSIST_HOME"
"$TRANSIST_BIN" workflows check --workflow ID@0.1.0 \
  --inputs-file /path/to/local-inputs.json --home "$TRANSIST_HOME"
"$TRANSIST_BIN" workflows authorize --workflow ID@0.1.0 \
  --inputs-file /path/to/local-inputs.json --home "$TRANSIST_HOME"
"$TRANSIST_BIN" workflows check --workflow ID@0.1.0 \
  --inputs-file /path/to/local-inputs.json --output /path/to/readiness.json --home "$TRANSIST_HOME"
```

Authorize only after readiness failures are exclusively the exact missing
capabilities. Fix schema, dependency, trust and input failures first. Installation
does not grant authority, import roots, bind inputs or create a run.

Execution is a separate, deliberate decision after successful readiness:

```sh
"$TRANSIST_BIN" workflows run --workflow ID@0.1.0 \
  --inputs-file /path/to/local-inputs.json --readiness-file /path/to/readiness.json \
  --trusted-execution --home "$TRANSIST_HOME"
```

Review manual gates explicitly, with actor and reason. Inspect durable run state
with `runs show`, `runs preflight` and `runs tail`. A source correction requires
a new package and fresh run; retry cannot replace a run's frozen recipe. To
roll back an example, retain prior immutable versions and stop initiating the
new version; do not rewrite existing run records.
