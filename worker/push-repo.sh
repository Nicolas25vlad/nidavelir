#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
task_branch="${NIDAVELIR_TASK_BRANCH:?NIDAVELIR_TASK_BRANCH is required}"

cd "$workspace"
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/usr/local/bin/nidavelir-git-askpass

git push --quiet --set-upstream origin "HEAD:refs/heads/$task_branch"
printf 'NIDAVELIR_PUSHED=%s\n' "$task_branch"
