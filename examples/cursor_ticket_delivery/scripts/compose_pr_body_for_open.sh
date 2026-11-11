#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  compose_pr_body_for_open.sh \
    --source-body-file repo://workflow/PROJ-123/pr_body_prepared.md \
    --output-body-file repo://workflow/PROJ-123/pr_body_for_open.md \
    [--include-transist-pr-callout true|false] \
    [--runtime-metadata-file /abs/path/to/transist-runtime-metadata.json] \
    [--repo-root /abs/path/to/repo]
USAGE
  exit 2
}

resolve_workflow_path() {
  local candidate="${1:-}"
  local repo_root="${2:-}"
  case "$candidate" in
    repo://*)
      if [ -z "$repo_root" ]; then
        echo "repo_root is required when using repo:// artifact paths" >&2
        exit 1
      fi
      printf '%s/.transist/%s\n' "${repo_root%/}" "${candidate#repo://}"
      ;;
    /*)
      printf '%s\n' "$candidate"
      ;;
    *)
      printf '%s/%s\n' "${TRANSIST_WORKSPACE_DIR:-$PWD}" "$candidate"
      ;;
  esac
}

normalize_bool() {
  case "$(printf '%s' "${1:-false}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on)
      printf 'true\n'
      ;;
    *)
      printf 'false\n'
      ;;
  esac
}

strip_existing_callout() {
  local input_file=$1
  awk '
    $0 == "<!-- transist-pr-callout:start -->" { skipping = 1; next }
    $0 == "<!-- transist-pr-callout:end -->" { skipping = 0; next }
    !skipping { print }
  ' "$input_file"
}

render_callout() {
  local metadata_file="${1:-}"
  if [ -z "$metadata_file" ] || [ ! -f "$metadata_file" ]; then
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    return 0
  fi
  python3 - "$metadata_file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

runtime = data.get("runtime") or {}
workflow = data.get("workflow") or {}
plugins = data.get("plugins") or []

lines = []
runtime_version = str(runtime.get("version") or "").strip()
if runtime_version:
    lines.append(f"Runtime: `{runtime_version}`")

workflow_id = str(workflow.get("id") or "").strip()
workflow_version = str(workflow.get("version") or "").strip()
if workflow_id and workflow_version:
    lines.append(f"Workflow: `{workflow_id}@{workflow_version}`")
elif workflow_id:
    lines.append(f"Workflow: `{workflow_id}`")
elif workflow_version:
    lines.append(f"Workflow version: `{workflow_version}`")

plugin_refs = []
for plugin in plugins:
    if not isinstance(plugin, dict):
        continue
    name = str(plugin.get("name") or "").strip()
    version = str(plugin.get("version") or "").strip()
    if name and version:
        plugin_refs.append(f"`{name}@{version}`")
    elif name:
        plugin_refs.append(f"`{name}`")
    elif version:
        plugin_refs.append(f"`@{version}`")

if plugin_refs:
    lines.append("Plugins: " + ", ".join(plugin_refs))

if not lines:
    raise SystemExit(0)

print("<!-- transist-pr-callout:start -->")
print("> [!NOTE]")
print("> **Transist Runtime**")
for line in lines:
    print(f"> - {line}")
print("<!-- transist-pr-callout:end -->")
PY
}

source_body_file=""
output_body_file=""
include_transist_pr_callout="false"
runtime_metadata_file="${TRANSIST_RUNTIME_METADATA_FILE:-}"
repo_root=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --jira-ticket-id|--jira-site-url)
      # Accept deprecated workflow args so stale materialized recipes keep working.
      shift 2
      ;;
    --source-body-file)
      source_body_file="${2:-}"
      shift 2
      ;;
    --output-body-file)
      output_body_file="${2:-}"
      shift 2
      ;;
    --include-transist-pr-callout)
      include_transist_pr_callout="${2:-}"
      shift 2
      ;;
    --runtime-metadata-file)
      runtime_metadata_file="${2:-}"
      shift 2
      ;;
    --repo-root)
      repo_root="${2:-}"
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

if [ -z "$source_body_file" ] || [ -z "$output_body_file" ]; then
  usage
fi

source_body_file=$(resolve_workflow_path "$source_body_file" "$repo_root")
output_body_file=$(resolve_workflow_path "$output_body_file" "$repo_root")
if [ -n "$runtime_metadata_file" ]; then
  runtime_metadata_file=$(resolve_workflow_path "$runtime_metadata_file" "$repo_root")
fi

mkdir -p "$(dirname "$output_body_file")"

body_tmp=$(mktemp "${TMPDIR:?}/compose-pr-body.XXXXXX")
footer_tmp=$(mktemp "${TMPDIR:?}/compose-pr-footer.XXXXXX")
trap 'rm -f "$body_tmp" "$footer_tmp"' EXIT

strip_existing_callout "$source_body_file" > "$body_tmp"
cat "$body_tmp" > "$output_body_file"

if [ "$(normalize_bool "$include_transist_pr_callout")" = "true" ]; then
  render_callout "$runtime_metadata_file" > "$footer_tmp"
  if [ -s "$footer_tmp" ]; then
    {
      printf '\n\n'
      cat "$footer_tmp"
      printf '\n'
    } >> "$output_body_file"
  fi
fi
