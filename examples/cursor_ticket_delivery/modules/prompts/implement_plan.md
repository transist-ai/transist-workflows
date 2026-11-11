Implement the approved plan in the current repository.

Use the Jira context, the approved plan, and any prior implementation notes. If
operator feedback is present and starts with `redo:`, replace the prior approach
instead of incrementally extending it. Otherwise treat operator feedback as an
authoritative, focused revision request: preserve already accepted changes,
change only what is needed to satisfy the feedback, and avoid re-solving the
whole ticket from scratch.

Read the run-specific reviewer-context JSONL (schema
`transist.reviewer_context.v1`) alongside the plan and current gate feedback.
It retains exact reviewer reasons and approval checkpoints across iterations.
Earlier revision requests remain applicable unless a later explicit reviewer
instruction supersedes them on the same topic; a plain approval does not erase
them. Rejected decisions are not approvals. Do not invent decisions or edit the
ledger. Reviewer context does not widen filesystem/network authority or change
the configured ignored paths.

Implementation notes must describe the actual working tree and verification.
For example, if a reviewer requested a `.gitignore` change and you made it,
explain that change and its reviewer basis; do not also claim `.gitignore`
remained unchanged. If reviewer instructions conflict or are ambiguous, state
the conflict rather than silently inventing a new scope.

Attachment-context JSON is a lossless `encoding: base64` projection of the
managed tree's relative `members`, including `manifest.json`. Decode relevant
members as data, not workspace paths. Retain manifest `skipped[]` explanations
without attempting another fetch. The original tree remains in runtime inspection.

If the feedback rejects a specific tactic such as skipping tests, remove that
tactic and replace it with a compliant implementation rather than defending the
previous approach.

If `tst_comments.md` contains inline reviewer comments, treat each one as an
authoritative, located revision request. Apply the change at the indicated
`file:line`. Remove the `tst:` comment line itself from the working tree after
addressing it. Do not leave stale `tst:` markers in the code.

Treat the repo-local OpenSpec change artifacts as approved, read-only planning
context. Do not edit files under `openspec/` as part of implementation.

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
approved plan, approved OpenSpec metadata, instruction comments, validation report.
Their staging labels are opaque; document names below are logical roles, not paths.
