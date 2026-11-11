Draft the final GitHub pull request description for the current implementation
repository.

All source material is already loaded in the context sections above. Do NOT
use Read, Write, or any other filesystem tools — work exclusively from the
context already provided.

Names below are logical document roles, not paths. Private staging labels are
opaque. Sections appear in this exact order: Jira issue, approved plan, PR header,
approved PR body, repository PR template. Use this order to identify the sections.

The context sections supply:

- `pr_body_header.md`: exact header lines that must appear at the top of the
  final PR body
- `pr_body.md`: the authoritative source PR body produced from the latest
  approved `implementation_loop` pass
- `plan.md`: the reviewed and approved development plan
- `jira_issue.json`: the Jira-backed ticket context
- `pull_request_template.md`: the repo-local PR template; this context section
  is empty when the target repo does not define `/.github/pull_request_template.md`

Requirements:

- Output markdown only, with no preamble and no code fences unless the source
  material already requires them.
- Do not include the Transist runtime callout.
- If the `pull_request_template.md` context section is empty, start with the
  exact non-empty content from `pr_body_header.md`, add a blank line, and then
  emit the current default body from `pr_body.md`.
- If the `pull_request_template.md` context section is not empty, the template
  structure takes precedence. Do not prepend `pr_body_header.md` as a standalone block before
  the template; instead integrate its content into the template's appropriate
  fields — for example, substitute the Jira ticket link into the template's
  "Addresses" placeholder. Keep all template structure, headings, checklist
  items, HTML comments, and any unmatched prompts intact.
- Fill the template's narrative sections from `plan.md` and `pr_body.md`.
  Prefer `plan.md` for "why" or intent and `pr_body.md` for concrete planned
  changes, verification, and risks.
- Keep all checklist boxes unchecked.
- If the template has no natural place for verification or risk content, append
  `## Verification` and `## Risks` sections after the template content using
  the facts already present in `pr_body.md`.
- Do not invent tests, files, or behavior that are not supported by the source
  artifacts.
