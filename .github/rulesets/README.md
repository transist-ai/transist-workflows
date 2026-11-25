# GitHub protection snapshots

These JSON files describe the intended post-cutover `transist-ai/transist-workflows`
rulesets and selected repository settings. They **do not apply themselves**:
checking them in, merging a PR, or running CI does not configure GitHub. Live
repository settings and inherited rules remain authoritative and may differ
until the separately authorized rollout is complete.
Each ruleset contains only `name`, `target`, `enforcement`, `conditions`, `rules`
and `bypass_actors`. API response IDs, timestamps and links are omitted; the
required check's `integration_id` is retained because it binds the check to its
actual GitHub App. The separate [repository settings](../repository-settings.json)
contain only the selected repository-level PATCH fields, not a ruleset wrapper.

## Effective protections

- `linear-pr-branches` requires linear history on branches other than the default
  branch and literal `main`. Keep PR branches current by **rebasing**, without
  merge commits. After authorization to rewrite your PR branch, publish the
  rebased commits with `git push --force-with-lease`; never force-push `main`.
- `main-branch-protection` separately protects the default branch: no deletion or
  non-fast-forward updates, linear history, a PR with resolved review threads,
  and the actual GitHub Actions **`Static checks`** status check, with strict
  up-to-date checking. There is no minimum approving-review count. A local check
  or a differently named job does not satisfy the required GitHub check.
- The `main-dco-signoff` snapshot targets literal `main` and is intended to be
  disabled after cutover. Until an administrator disables the live ruleset, its
  commit-message requirement remains in force. The new `main-dco` workflow checks
  new `main` commits after push; it is not a required PR check or merge block.
  See [CONTRIBUTING](../../CONTRIBUTING.md) for the merger's DCO responsibility.
- Squash is the only final PR merge method. Rebase PR updates locally; squash
  only at final integration. Repository settings disable merge commits, rebase
  merges and auto-merge, allow branch updates, retain merged branches, and intend
  to disable web commit sign-off after cutover. The final squash title uses `COMMIT_OR_PR_TITLE` and its
  body uses `COMMIT_MESSAGES`; review the final message and DCO trailers.
- `v-tag-protection` makes existing `v*` tags immutable: no updates, force updates,
  or deletion. Tag creation is not blocked by this ruleset.
- The other three ruleset snapshots remain active, all with empty `bypass_actors`:
  no configured bypass, including for maintainers.

## Staged DCO rollout

1. An administrator rechecks repository visibility, settings, and effective rules,
   including inherited rules and required checks, saves rollback settings, and
   obtains approval. Stop on unexplained drift.
2. Merge the rollout PR while the existing `main-dco-signoff` rule remains active;
   preserve genuine sign-offs in the final squash message.
3. Confirm a green `main-dco` run on that merge SHA before separately disabling
   the live `main-dco-signoff` ruleset. Do not require `main-dco` on PRs or
   release gates. Set `web_commit_signoff_required` to false only as an authorized
   administrative change; preserve all unrelated protections.
4. Verify effective live settings and, on the first approved post-cutover PR,
   confirm unsigned feature commits pass `Static checks`, then verify the signed
   squash commit passes `main-dco`. Do not rewrite pre-rollout history or tags.

If `main-dco` fails, stop further merges and notify a maintainer with the failing
SHA and run URL. Do not force-push `main`; a later signed commit does not repair
an earlier unsigned commit.

## Refresh from GitHub (read-only API calls)

From the repository root, with authenticated `gh`, export the live objects.
Resolve each name uniquely to its current ID rather than checking API IDs into
the snapshot. This writes local files only; review the resulting diff. During
rollout it will replace intended final values with live values, which may still
show the old protections; do not mistake that refresh for cutover.

```sh
set -eu
repo=transist-ai/transist-workflows
for name in linear-pr-branches main-branch-protection main-dco-signoff v-tag-protection; do
  id="$(gh api "repos/$repo/rulesets" --paginate --jq \
    ".[] | select(.name == \"$name\") | .id")"
  case "$id" in ''|*[!0-9]*) exit 1 ;; esac
  gh api "repos/$repo/rulesets/$id" \
    --jq '{name,target,enforcement,conditions,rules,bypass_actors}' \
    > ".github/rulesets/$name.json"
done
gh api "repos/$repo" \
  --jq '{allow_merge_commit,allow_squash_merge,allow_rebase_merge,allow_auto_merge,allow_update_branch,delete_branch_on_merge,web_commit_signoff_required,squash_merge_commit_title,squash_merge_commit_message}' \
  > .github/repository-settings.json
```

Do not export the whole repository response: it includes unrelated metadata.
Validate JSON and run the static gate documented in `CONTRIBUTING.md` after refresh.

## Applying a separately authorized administrative change

A refresh does not authorize changing GitHub. If an administrator is explicitly
authorized to apply a reviewed snapshot, first resolve the **existing** ruleset
by its exact name and require one match, then update that ID with `PUT`:

```sh
repo=transist-ai/transist-workflows
name=main-branch-protection
id="$(gh api "repos/$repo/rulesets" --paginate --jq \
  ".[] | select(.name == \"$name\") | .id")" || exit 1
case "$id" in ''|*[!0-9]*) exit 1 ;; esac
gh api --method PUT "repos/$repo/rulesets/$id" \
  --input ".github/rulesets/$name.json"
```

Repeat the lookup for each intended ruleset. Stop on missing or ambiguous names;
never blindly `POST` duplicates. Repository settings are a separate operation:

```sh
gh api --method PATCH "repos/$repo" --input .github/repository-settings.json
```

After an authorized change, re-export both surfaces and compare them to the
reviewed snapshots. No workflow in this directory applies these files.
