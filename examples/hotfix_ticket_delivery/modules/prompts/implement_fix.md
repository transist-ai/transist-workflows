Implement the fix described in the Jira ticket in the current repository.

Use the Jira context and any prior implementation notes. If operator feedback
is present and starts with `redo:`, replace the prior approach instead of
incrementally extending it. Otherwise treat operator feedback as an
authoritative, focused revision request: preserve already accepted changes,
change only what is needed to satisfy the feedback, and avoid re-solving the
whole ticket from scratch.

The attachment-context JSON contains a lossless `encoding: base64` projection of
the managed attachment tree's relative `members`, including `manifest.json`.
Decode relevant members as data; do not interpret member names as workspace paths.
Manifest `skipped[]` entries were intentionally not downloaded; do not fetch them.
The original bounded tree remains in runtime document inspection outside Git.

If the feedback rejects a specific tactic such as skipping tests, remove that
tactic and replace it with a compliant implementation rather than defending the
previous approach.

If `tst_comments.md` contains inline reviewer comments, treat each one as an
authoritative, located revision request. Apply the change at the indicated
`file:line`. Remove the `tst:` comment line itself from the working tree after
addressing it. Do not leave stale `tst:` markers in the code.

Make the required repository changes. Then return markdown with:

- first non-empty line: one plain-text line ≤72 characters, imperative mood,
  summarizing the change; no Jira prefix, no markdown
- `## What Changed`
- `## Verification`
- `## Risks`

The first line is used verbatim as the git commit message — it must be a single
plain-text line ≤72 characters, imperative mood (e.g. "Add retry logic for
network calls"), no Jira prefix, no markdown. Do not write reasoning or preamble
before it. The pull request body will start at `## What Changed`.

Do not create git commits, do not push branches, do not open pull requests, and
do not rewrite git history. Leave repository changes only in the working tree.
The dedicated Transist git and GitHub steps handle commit, push, and PR
creation later in the workflow.
Context sections are ordered: reviewer ledger, Jira issue, attachment projection,
instruction comments. Their staging labels are opaque; names below are roles,
not workspace file paths. The current draft may be included separately as feedback.
