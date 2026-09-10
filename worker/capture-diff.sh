#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
base_branch="${NIDAVELIR_BASE_BRANCH:-main}"

cd "$workspace"
base_ref="origin/$base_branch"
base_commit="$(git merge-base "$base_ref" HEAD)"
commit="$(git rev-parse HEAD)"
stat="$(git diff --stat "$base_commit"...HEAD)"
patch="$(git diff --binary --no-ext-diff "$base_commit"...HEAD)"

jq -n \
  --arg base_commit "$base_commit" \
  --arg commit "$commit" \
  --arg stat "$stat" \
  --arg patch "$patch" \
  '{base_commit: $base_commit, commit: $commit, stat: $stat, patch: $patch}'
