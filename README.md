# Transist Workflows

Self-contained example workflows for the [Transist runtime](https://github.com/transist-ai/transist).
These are reviewed **authored sources**, not a signed workflow distribution.
Examples use Apache-2.0; the runtime is a separate MPL-2.0 project.

**Experimental source-only release.** Runtime 0.1.1 source validation and selected
synthetic regressions do not establish production or live-provider readiness.
Full installed-example/authoring-fixture acceptance is deferred because the pinned
peer helper has known Linux and macOS failures. See [validation limits](docs/validation.md).

## Examples

| Example | Demonstrates | Requirements and effects |
| --- | --- | --- |
| [Edge fault advisory](examples/edge_fault_advisory/README.md) | Read → managed diagnostic review → model → managed response | Shell and OpenAI-compatible plugins; sends exact reviewed bytes to OpenRouter only after approval |
| [Agent plugin canary](examples/ai_agent_plugins_canary/README.md) | Seven model/CLI participants with action-bound setting profiles | Provider CLIs, models and authentication; external calls, local Ollama, and Cursor state writes |
| [Cursor ticket delivery](examples/cursor_ticket_delivery/README.md) | Planning, review gates, implementation, validation and PR delivery | Jira, Cursor, OpenSpec, Git and GitHub; modifies a repository, commits, pushes, merges and cleans branches |
| [Hotfix ticket delivery](examples/hotfix_ticket_delivery/README.md) | Direct implementation and PR remediation without plan generation | Jira, Copilot, Git and GitHub; modifies a repository, commits, pushes, merges and cleans branches |

Start with the runtime's [offline quickstart](https://github.com/transist-ai/transist/blob/v0.1.1/docs/public/guides/getting-started/quickstart.md).
Then read an example's prerequisites and effects before installing it. Ticket
delivery examples are advanced integrations, not safe defaults for an arbitrary
repository. Use a disposable test repository and service project first.

## Author through your assistant

Load the runtime's checked-out `transist-workflow-authoring` skill and references.
Capture intent → clarify missing decisions/bindings → inspect real action
contracts → generate → validate source → explain/compare → present prerequisites
and request execution approval separately. See the
[public authoring guide](https://github.com/transist-ai/transist/blob/v0.1.0/docs/public/guides/authoring/ai-assisted-authoring-with-repo-skills.md).
Missing integrations must be reported, not invented or hidden in unrestricted shell.

[Conversational authoring fixtures](tests/fixtures/conversational_authoring/README.md)
provide three executable synthetic tasks and recorded assistant walkthroughs:
diagnostic advisory, approved draft publication and its two-approval revision.
They are registered tests, separate from the four maintained examples. Their
dedicated runner uses real selected plugin packages with fake model/publication
peers. It is also mandatory in the unfiltered installed runner. Current acceptance
status is in [validation](docs/validation.md). Synthetic decisions do not claim
human execution approval.

## Ticket-delivery storage before launch

Both delivery definitions use root managed documents for ticket payloads,
attachment trees, plans/notes, review context, PR drafts, retry state and reviewer
ledgers. They live outside the target Git workspace. Process actions receive
private staged copies; successful publication retains immutable revisions.
Resume preserves committed documents; replay starts a fresh namespace and ledger
identity. No caller storage prefix, generated ledger ID or workspace exclusion
is needed for this storage. Never persist secrets in documents or workspace files.

Only source changes and Cursor's `openspec/changes/` bundles are intended workspace
deliverables. The pre-generation/pre-commit guard still rejects stageable legacy
operational/interaction files without editing the target's ignore rules. Reviewing
managed documents does not snapshot or authorize arbitrary workspace mutations.

Independent runs of the same ticket have isolated documents, but **mutations of
the same Git workspace still require coordination**. Documents do not rollback
Git changes or external Jira/GitHub effects. Invocation scratch (`run://`) remains
unsuitable for cross-step storage.

The initial authored workflow/module releases and plugin pins use `0.1.0`.
After publication, workflows and modules can release independently with SemVer,
including prerelease and build metadata; plugin pins must specify exact SemVer
versions. Published versioned payloads are immutable: changed bytes need a new
version and, for signed packages, a new signature. Schema identifiers remain
`transist.flow.v1` and `transist.module.v1`. See [scripts/README.md](scripts/README.md)
for validation.
The narrowed publication gate checks all four example sources on native macOS.
Its recorded results predate the seven-provider canary target and are historical
evidence, not validation of additional providers or current bytes.
Full installed coverage of four examples and three authoring fixtures on both
platforms remains deferred, not passed.
See [validation](docs/validation.md) for observed results and
[compatibility](docs/compatibility.md) for exact published dependency identities.
Use fresh disposable homes; historical signed packages do not validate these bytes.

## Setup and compatibility

The recorded compatibility baseline is the published **Transist 0.1.1** release
and public plugins `v0.1.0`; later independent releases require their own validation.
Select the executable explicitly; do not assume the version on `PATH` matches.
See [compatibility](docs/compatibility.md) for source revisions, exact plugin
pins, build prerequisites, and the distinction between static and live checks.

Install Python development dependencies in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

To validate source without running examples:

```sh
.venv/bin/python scripts/check_examples.py \
  --transist /absolute/path/to/transist \
  --plugins-dir /absolute/path/to/transist-plugins \
  --home-base "$PWD/tmp" \
  --example edge_fault_advisory --example ai_agent_plugins_canary
```

Create the ignored `tmp` directory first if needed. Checks use disposable homes,
synthetic workspaces and no service credentials; they do not establish live
readiness. Plugin source lives in the separate
[public plugin repository](https://github.com/transist-ai/transist-plugins), not
inside these examples.

For actual use, follow the individual README. Standalone homes accept unsigned
source and have permissive policy. For signed, explicitly authorized delivery,
follow [governed use](docs/governed-use.md). Installation, readiness, authority,
and execution are separate operations.

## Contributing and publication

See [CONTRIBUTING.md](CONTRIBUTING.md) for tests, safety and DCO sign-off.
[Validation tooling](scripts/README.md) documents offline checks and the
current-content publication gate. Automatic CI is **static-only**: it does not run
tests, build adapters, install plugins or invoke Transist. Full native validation
is a separate maintainer gate. Follow [publication](docs/publication.md) to export
only approved source; never copy development history or local state.
