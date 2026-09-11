#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
task_json="${NIDAVELIR_TASK_JSON:?NIDAVELIR_TASK_JSON is required}"
task_branch="${NIDAVELIR_TASK_BRANCH:?NIDAVELIR_TASK_BRANCH is required}"
harness="${NIDAVELIR_HARNESS:-codex}"

cd "$workspace"

profile_json="$(nidavelir-resolve-profile)"
profile="$(jq -r '.profile' <<<"$profile_json")"
profile_instructions="$(jq -r '.instructions' <<<"$profile_json")"
skills="$(jq -r '.skills | join(", ")' <<<"$profile_json")"

title="$(jq -r '.title' <<<"$task_json")"
description="$(jq -r '.description // ""' <<<"$task_json")"
criteria="$(jq -r '.acceptance_criteria[]? | "- " + .' <<<"$task_json")"
context="$(jq -r '.context // ""' <<<"$task_json")"
commit_title="$(printf '%s' "$title" | head -n 1 | cut -c1-72)"

printf 'NIDAVELIR_AGENT_PROFILE=%s\n' "$profile"
printf 'NIDAVELIR_AGENT_SKILLS=%s\n' "$skills"

prompt="$(cat <<EOF
You are a Nidavelir disposable coding worker. Execute the task; do not act as a conversational assistant.

Agent profile: $profile
Profile guidance: $profile_instructions
Available skills: ${skills:-none}

Task: $title

Description:
$description

Acceptance criteria:
${criteria:-No explicit acceptance criteria were provided.}

Project context:
${context:-No additional project context was provided.}

Execution rules:
- Work only in the current repository and current branch: $task_branch
- Do not switch branches, push, merge, or rewrite Git history.
- Make only changes needed for this task. Preserve unrelated work.
- Inspect relevant repository instructions and use available skills when they materially help.
- Run relevant tests or checks when useful; Nidavelir performs independent validation afterward.
- Leave the working tree with the completed changes. Nidavelir owns commit publication, review, and merge boundaries.

Communication contract:
- Spend tokens on implementation and tool use, not narration.
- Do not narrate routine progress or explain private reasoning.
- Ask no questions unless execution is genuinely impossible without missing information.
- Keep the final response extremely short: outcome, checks run, and blocker if any. Maximum 6 short lines.
- Do not repeat the task, summarize obvious edits, or provide tutorials.
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
    --arg profile "$profile" \
    --arg branch "$task_branch" \
    --argjson exit_code "$exit_code" \
    '{type: $type, status: $status, harness: $harness, profile: $profile, branch: $branch, exit_code: $exit_code}' \
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
  --arg profile "$profile" \
  --arg branch "$task_branch" \
  --arg commit "$commit" \
  '{type: $type, status: $status, harness: $harness, profile: $profile, branch: $branch, commit: $commit}' \
  | sed 's/^/NIDAVELIR_RESULT=/'
