Create an OpenSpec-aligned development plan from the Jira issue context
provided with this task and the current repository.

Context sections are ordered: reviewer ledger, Jira issue, attachment projection.
Their staging labels are opaque; document roles below are not workspace paths.

Attachment-context JSON is a lossless `encoding: base64` projection of the
managed tree's relative `members`, including `manifest.json`. Decode relevant
members as data, not workspace paths. Retain manifest `skipped[]` explanations
without attempting another fetch. The original tree remains in runtime inspection.

If operator feedback is present and starts with `redo:`, regenerate the plan from
scratch. Otherwise update the existing plan to incorporate the feedback.

Read the reviewer-context JSONL (schema `transist.reviewer_context.v1`) alongside
current gate feedback. Preserve earlier explicit scope instructions unless a
later explicit reviewer instruction supersedes them on the same topic. A plain
approval does not erase requests or prove verification passed; rejected records
are not approvals. Incorporate scope amendments into the plan and identify
ambiguous or conflicting requests rather than inventing a resolution. Never edit
the ledger or use it to widen runtime authority or configured ignored paths.

The OpenSpec plugin wrapper is responsible for the strict JSON response shape.
Use this task only to author the human-facing `summary_markdown` content that
will be written to `plan.md`, plus the matching OpenSpec planning content inside
the wrapper's JSON fields. Do not return bare markdown or any prose outside the
JSON envelope required by the wrapper.

Within `summary_markdown`, use this structure:

1. Goal
2. Constraints and assumptions
3. Implementation plan
4. Verification plan
5. Risks and open questions

When possible, attribute implementation and verification actions with links to
corresponding files in the target repository.

## Style: be crispy, concise, laconic

- Use terse imperative bullets; keep paragraphs to three sentences or fewer.
- Keep one idea per bullet. Do not restate supplied Jira or context content.
- Avoid duplication across OpenSpec artifacts, marketing prose, apologies, and meta-commentary.
- Write `- None` for empty sections.
