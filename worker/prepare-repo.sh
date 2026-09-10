#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
repository="${NIDAVELIR_REPOSITORY:?NIDAVELIR_REPOSITORY is required}"
base_branch="${NIDAVELIR_BASE_BRANCH:-main}"
task_branch="${NIDAVELIR_TASK_BRANCH:?NIDAVELIR_TASK_BRANCH is required}"

case "$repository" in
  http://*|https://*) repo_url="${repository%.git}.git" ;;
  *) repo_url="https://github.com/${repository%.git}.git" ;;
esac

mkdir -p "$workspace"
find "$workspace" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

export GIT_TERMINAL_PROMPT=0
if [[ -n "${NIDAVELIR_GITHUB_TOKEN:-}" ]]; then
  export GIT_ASKPASS=/usr/local/bin/nidavelir-git-askpass
fi

git clone --quiet --branch "$base_branch" --single-branch "$repo_url" "$workspace"
cd "$workspace"
git config user.name "${NIDAVELIR_GIT_AUTHOR_NAME:-Nidavelir Agent}"
git config user.email "${NIDAVELIR_GIT_AUTHOR_EMAIL:-nidavelir@localhost}"

if git ls-remote --exit-code --heads origin "$task_branch" >/dev/null 2>&1; then
  git fetch --quiet origin "$task_branch:$task_branch"
  git switch "$task_branch"
else
  git switch -c "$task_branch"
fi

chown -R 10001:10001 "$workspace"
printf 'NIDAVELIR_PREPARED=%s\n' "$task_branch"
