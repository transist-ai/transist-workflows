---
name: code-changes
description: Use when implementing a development plan, when changing a repo's source code.
---

<!-- Example skill file, exists to show the usage in the example workflow.
     Do not expect it to be a production-ready skill file.
     An AI agent, though, should apply this skill during example workflow run. -->

# Changes implementation

When implementing changes, make sure to follow the coding style of the project, and to write tests for your changes.
Whenever possible - spawn sub-agents to implement changes in parallel.

For maintained Transist catalog assets, workflow/module releases and exact plugin
pins use `0.1.0`. Keep schema identifiers `transist.flow.v1` and
`transist.module.v1` unchanged; only explicitly identified negative/version-policy
fixtures are exempt. Validate edited packages in fresh disposable homes without
replacing installed same-version payloads.

# Changes validation

Read the supplied context files before editing. They are private staged copies
of root managed documents outside the Git workspace. Preserve their exact bytes;
do not delete, stage, commit or publish them. Never relocate shared context to
`run://`: it is invocation-private scratch removed after invocation. The runtime
owns revision publication and recovery; source changes belong in the workspace.
Never persist secrets in workspace files, prompts, logs or artifacts. Intentional
repository deliverables are distinct from operational files and must be reviewed
normally. Leave commits, pushes and PR operations to dedicated workflow steps;
validate implementation changes without committing them here.

Before completing implementation, run the target repository's documented compile, lint, and test checks. Do not create commits in an agent step.
