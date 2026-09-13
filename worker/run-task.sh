#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
task_json="${NIDAVELIR_TASK_JSON:?NIDAVELIR_TASK_JSON is required}"
task_branch="${NIDAVELIR_TASK_BRANCH:?NIDAVELIR_TASK_BRANCH is required}"
harness="${NIDAVELIR_HARNESS:-codex}"
reasoning_effort="${NIDAVELIR_CODEX_REASONING_EFFORT:-low}"
model_verbosity="${NIDAVELIR_CODEX_VERBOSITY:-low}"
tool_output_limit="${NIDAVELIR_CODEX_TOOL_OUTPUT_TOKEN_LIMIT:-4000}"
project_doc_max_bytes="${NIDAVELIR_CODEX_PROJECT_DOC_MAX_BYTES:-16384}"

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

configured_validation_count="$(jq '.validation_commands // [] | length' <<<"$task_json")"
if (( configured_validation_count > 0 )); then
  validation_plan="$(jq -c '{mode:"configured",reason:"validation commands configured on task",commands:(.validation_commands // []),notes:[]}' <<<"$task_json")"
else
  validation_plan="$(nidavelir-detect-validation)"
fi

printf 'NIDAVELIR_AGENT_PROFILE=%s\n' "$profile"
printf 'NIDAVELIR_AGENT_SKILLS=%s\n' "$skills"
printf 'NIDAVELIR_VALIDATION_MODE=%s\n' "$(jq -r '.mode' <<<"$validation_plan")"
printf 'NIDAVELIR_TOKEN_POLICY=reasoning:%s verbosity:%s tool_output:%s project_docs:%s\n' \
  "$reasoning_effort" "$model_verbosity" "$tool_output_limit" "$project_doc_max_bytes"

# Keep the stable policy/profile prefix before task-specific text so provider prompt caching
# can reuse as much input as possible across workers with the same profile.
prompt="Nidavelir coding worker. Implement; do not chat.\nProfile: ${profile_instructions}\nRules:\n- Stay on the current repo/branch; never push, merge, switch branches, or rewrite history.\n- Change only what is required. Read repo instructions/skills only when relevant.\n- Run useful checks; Nidavelir validates independently. Leave completed changes in the working tree.\n- No progress narration/reasoning recap. Final: outcome, checks, blocker if any; max 4 short lines.\n\nTask: ${title}"
[[ -n "$description" ]] && prompt+=$'\n\n'"$description"
[[ -n "$criteria" ]] && prompt+=$'\n\nAcceptance:\n'"$criteria"
[[ -n "$context" ]] && prompt+=$'\n\nContext:\n'"$context"

usage_json='null'

case "$harness" in
  codex)
    harness_version="$(codex --version | head -n 1)"
    printf 'NIDAVELIR_HARNESS_VERSION=%s\n' "$harness_version"
    events_file="$(mktemp)"
    trap 'rm -f "${events_file:-}"' EXIT
    set +e
    codex \
      --dangerously-bypass-approvals-and-sandbox \
      -c "model_reasoning_effort=\"$reasoning_effort\"" \
      -c "model_verbosity=\"$model_verbosity\"" \
      -c 'model_reasoning_summary="none"' \
      -c "tool_output_token_limit=$tool_output_limit" \
      -c "project_doc_max_bytes=$project_doc_max_bytes" \
      exec --json "$prompt" | tee "$events_file"
    exit_code=${PIPESTATUS[0]}
    set -e
    usage_json="$(jq -s '
      [ .[] | select(.type == "turn.completed") | .usage ]
      | reduce .[] as $u (
          {input_tokens:0,cached_input_tokens:0,cache_write_input_tokens:0,output_tokens:0,reasoning_output_tokens:0,total_tokens:0};
          .input_tokens += ($u.input_tokens // 0)
          | .cached_input_tokens += ($u.cached_input_tokens // 0)
          | .cache_write_input_tokens += ($u.cache_write_input_tokens // 0)
          | .output_tokens += ($u.output_tokens // 0)
          | .reasoning_output_tokens += ($u.reasoning_output_tokens // 0)
          | .total_tokens += (($u.input_tokens // 0) + ($u.output_tokens // 0))
        )
    ' "$events_file" 2>/dev/null || printf 'null')"
    ;;
  cursor)
    harness_version="$(agent --version | head -n 1)"
    printf 'NIDAVELIR_HARNESS_VERSION=%s\n' "$harness_version"
    set +e
    agent -p "$prompt" --output-format json --force
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
    --argjson token_usage "$usage_json" \
    --argjson validation_plan "$validation_plan" \
    '{type: $type, status: $status, harness: $harness, profile: $profile, branch: $branch, exit_code: $exit_code, token_usage: $token_usage, validation_plan: $validation_plan}' \
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
  --argjson token_usage "$usage_json" \
  --argjson validation_plan "$validation_plan" \
  '{type: $type, status: $status, harness: $harness, profile: $profile, branch: $branch, commit: $commit, token_usage: $token_usage, validation_plan: $validation_plan}' \
  | sed 's/^/NIDAVELIR_RESULT=/'
