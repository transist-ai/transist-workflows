# Public compatibility baseline

Use the published **Transist 0.1.1** runtime and matching admin binary, and a clean
checkout of the public plugin release. Verify downloaded archives with the
release's checksums and Minisign procedure before selecting explicit executables.
Version output alone is not provenance.

| Component | Release | Exact commit |
| --- | --- | --- |
| [Runtime](https://github.com/transist-ai/transist/releases/tag/v0.1.1) | `v0.1.1` | `da0d54b02eadb1cae323bd8fdf27864c73a43a3c` |
| [Plugins](https://github.com/transist-ai/transist-plugins/releases/tag/v0.1.0) | `v0.1.0` | `3744f23b2a6f9e87a8847944a1d614668db423e0` |

All maintained workflow/module versions and exact plugin pins are `0.1.0`.
Schemas remain `transist.flow.v1` and `transist.module.v1`. Changed same-version
bytes require a new reviewed package and fresh home; never overwrite an installed
payload. This repository distributes unsigned authored source, not signed bundles.

Runtime 0.1.1 fixes bounded-loop successor routing for newly compiled recipes.
Compile new recipes and start new runs in fresh homes to adopt it. Previously
prepared recipes without routing metadata keep legacy behavior on resume/replay;
never retrofit persisted recipes or strip routing metadata. Preserve each preceding
runtime/home pair and reviewed bundle for recovery. Rollback returns to that
matching pair and does not undo external effects.

| Example | Plugins, each at `0.1.0` |
| --- | --- |
| `edge_fault_advisory` | `shell`, `openai.compatible` |
| `ai_agent_plugins_canary` | `anthropic`, `cursor.cli`, `github.copilot.cli`, `ollama.cli`, `opencode.cli` |
| `cursor_ticket_delivery` | `cursor.cli`, `git.cli`, `github.cli`, `jira.rest`, `openspec`, `shell` |
| `hotfix_ticket_delivery` | `git.cli`, `github.cli`, `github.copilot.cli`, `jira.rest`, `shell` |

Workflow YAML is authoritative. Source checks install selected contracts in fresh
disposable homes and may build the Ollama adapter using a real Go toolchain.
They dispatch no workflow. Automatic CI only runs the separate static checker:
no builds, installation, unit/helper execution or runtime calls.

Full installed acceptance (deferred for this experimental release) requires
native macOS ARM64 and Linux ARM64, isolated Python
3.11, real Go, and the platform sandbox prerequisites. Linux namespace fixtures
need a dedicated privileged controller and root-owned source copies. macOS fixture
paths must be canonical and sandbox-visible, outside protected system temp roots.
No sandbox policy changes are part of validation.

The approved publication scope uses native macOS source validation and all five
synthetic hotfix runtime regressions with these exact public dependencies.
Earlier Linux results are historical evidence, not final-release-byte acceptance.

See [validation](validation.md) for current acceptance status and the complete
command inventory. [Archived evidence](history/compatibility-before-publication.md)
describes older development tuples only. Deterministic fake-provider tests do not
establish live account readiness, operational permission or governed trust.
