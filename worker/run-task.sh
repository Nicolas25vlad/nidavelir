#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
task_json="${NIDAVELIR_TASK_JSON:?NIDAVELIR_TASK_JSON is required}"
task_branch="${NIDAVELIR_TASK_BRANCH:?NIDAVELIR_TASK_BRANCH is required}"
harness="${NIDAVELIR_HARNESS:-codex}"

cd "$workspace"

title="$(jq -r '.title' <<<"$task_json")"
description="$(jq -r '.description // ""' <<<"$task_json")"
criteria="$(jq -r '.acceptance_criteria[]? | "- " + .' <<<"$task_json")"
context="$(jq -r '.context // ""' <<<"$task_json")"
commit_title="$(printf '%s' "$title" | head -n 1 | cut -c1-72)"

prompt="$(cat <<EOF
You are executing a Nidavelir coding task inside a disposable, externally isolated worker.

Task: $title

Description:
$description

Acceptance criteria:
${criteria:-No explicit acceptance criteria were provided.}

Project context:
${context:-No additional project context was provided.}

Constraints:
- Work only in the current repository and current branch: $task_branch
- Do not switch branches, push, merge, or rewrite Git history.
- Make only changes needed for this task.
- Run relevant tests or checks when useful.
- Leave the working tree with the completed changes. Nidavelir handles the commit and push boundary.
EOF
)"

case "$harness" in
  codex)
    harness_version="$(codex --version | head -n 1)"
    printf 'NIDAVELIR_HARNESS_VERSION=%s\n' "$harness_version"
    set +e
    codex --dangerously-bypass-approvals-and-sandbox exec --json "$prompt"
    exit_code=$?
    set -e
    ;;
  cursor)
    harness_version="$(agent --version | head -n 1)"
    printf 'NIDAVELIR_HARNESS_VERSION=%s\n' "$harness_version"
    set +e
    agent -p "$prompt" --output-format text --force
    exit_code=$?
    set -e
    ;;
  *)
    printf 'Unsupported Nidavelir harness: %s\n' "$harness" >&2
    exit 64
    ;;
esac

if (( exit_code != 0 )); then
  jq -cn \
    --arg type "nidavelir_result" \
    --arg status "failed" \
    --arg harness "$harness" \
    --arg branch "$task_branch" \
    --argjson exit_code "$exit_code" \
    '{type: $type, status: $status, harness: $harness, branch: $branch, exit_code: $exit_code}' \
    | sed 's/^/NIDAVELIR_RESULT=/'
  exit "$exit_code"
fi

git add -A
if ! git diff --cached --quiet; then
  git commit --quiet -m "task: $commit_title"
fi

commit="$(git rev-parse HEAD)"
jq -cn \
  --arg type "nidavelir_result" \
  --arg status "success" \
  --arg harness "$harness" \
  --arg branch "$task_branch" \
  --arg commit "$commit" \
  '{type: $type, status: $status, harness: $harness, branch: $branch, commit: $commit}' \
  | sed 's/^/NIDAVELIR_RESULT=/'
