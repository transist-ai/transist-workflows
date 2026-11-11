#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  sync_branch_before_feature_branch.sh \
    --repo-path /abs/path/to/repo \
    --remote origin \
    [--branch main]
EOF
  exit 2
}

repo_path=""
remote=""
branch=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo-path)
      repo_path="${2:-}"
      shift 2
      ;;
    --remote)
      remote="${2:-}"
      shift 2
      ;;
    --branch)
      branch="${2:-}"
      shift 2
      ;;
    -*)
      echo "unknown argument: $1" >&2
      usage
      ;;
    *)
      usage
      ;;
  esac
done

if [ -z "$repo_path" ] || [ -z "$remote" ]; then
  usage
fi

cd "$repo_path"

# Serialize trunk-fetch operations across concurrent invocations on the same
# repo. All git worktrees of "$repo_path" share the same .git directory, so
# parallel `git fetch` calls race on `refs/remotes/<remote>/<branch>` and
# `packed-refs`, producing errors like:
#   error: fetching ref refs/remotes/origin/main failed: incorrect old value provided
# `mkdir` is atomic on POSIX, so we use a lock directory inside .git as a
# cross-platform mutex (macOS does not ship `flock`). The lock is released on
# any script exit via the EXIT trap.
git_dir="$(git rev-parse --git-common-dir)"
case "$git_dir" in
  /*) lock_dir="$git_dir/.transist-trunk-sync.lock.d" ;;
  *)  lock_dir="$repo_path/$git_dir/.transist-trunk-sync.lock.d" ;;
esac

acquire_lock() {
  local waited=0
  local timeout="${TRANSIST_TRUNK_SYNC_LOCK_TIMEOUT_SECONDS:-300}"
  while ! mkdir "$lock_dir" 2>/dev/null; do
    if [ "$waited" -ge "$timeout" ]; then
      echo "timed out after ${timeout}s waiting for trunk-sync lock at $lock_dir" >&2
      exit 1
    fi
    sleep 1
    waited=$((waited + 1))
  done
  trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT INT TERM
}

acquire_lock

resolve_branch() {
  if [ -n "$branch" ]; then
    printf '%s\n' "$branch"
    return
  fi

  remote_head_ref=$(
    git ls-remote --symref "$remote" HEAD 2>/dev/null \
      | awk '/^ref:/ { sub("^refs/heads/", "", $2); print $2; exit }'
  )
  if [ -n "$remote_head_ref" ]; then
    printf '%s\n' "$remote_head_ref"
    return
  fi

  remote_head_ref=$(git symbolic-ref --quiet --short "refs/remotes/$remote/HEAD" 2>/dev/null || true)
  if [ -n "$remote_head_ref" ]; then
    printf '%s\n' "${remote_head_ref#"$remote/"}"
    return
  fi

  echo "could not resolve default branch for remote '$remote'; pass --branch explicitly" >&2
  exit 1
}

resolved_branch=$(resolve_branch)

# Fetch the trunk into the shared .git so that worktree creation downstream
# can use `<remote>/<resolved_branch>` as a stable start point. We deliberately
# do NOT `git switch` or `git pull` the main checkout: when this script runs
# concurrently for multiple feature worktrees of the same source repo, mutating
# the shared HEAD/working tree introduces extra contention with no benefit
# (each worktree is created from the freshly fetched remote-tracking ref).
git fetch "$remote" "$resolved_branch"

printf '%s/%s\n' "$remote" "$resolved_branch"
