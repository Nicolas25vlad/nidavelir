#!/usr/bin/env bash
set -euo pipefail

lock_file="${1:-/usr/local/lib/nidavelir-worker/skills.lock.json}"
store="${NIDAVELIR_SKILL_STORE:-/opt/nidavelir/skill-store}"
licenses="${NIDAVELIR_THIRD_PARTY_LICENSES:-/opt/nidavelir/third-party/licenses}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

mkdir -p "$store" "$licenses"

while IFS=$'\t' read -r source repo revision license_file; do
  source_dir="$work/$source"
  git init -q "$source_dir"
  git -C "$source_dir" remote add origin "$repo"
  git -C "$source_dir" fetch -q --depth 1 origin "$revision"
  git -C "$source_dir" checkout -q --detach FETCH_HEAD

  if [[ ! -f "$source_dir/$license_file" ]]; then
    printf 'nidavelir: missing license file %s for %s\n' "$license_file" "$source" >&2
    exit 65
  fi
  cp "$source_dir/$license_file" "$licenses/$source.txt"

  while IFS=$'\t' read -r skill path; do
    [[ -n "$skill" ]] || continue
    skill_dir="$source_dir/$path"
    if [[ ! -f "$skill_dir/SKILL.md" ]]; then
      printf 'nidavelir: pinned skill %s has no SKILL.md at %s\n' "$skill" "$path" >&2
      exit 65
    fi
    rm -rf "$store/$skill"
    cp -a "$skill_dir" "$store/$skill"
  done < <(jq -r --arg source "$source" '.skills[] | select(.source == $source) | [.id, .path] | @tsv' "$lock_file")
done < <(jq -r '.sources[] | [.id, .repository, .revision, .license_file] | @tsv' "$lock_file")

find "$store" -type d -exec chmod 0555 {} +
find "$store" -type f -exec chmod 0444 {} +
find "$licenses" -type f -exec chmod 0444 {} +
