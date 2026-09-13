#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
profiles_file="${NIDAVELIR_PROFILES_FILE:-$script_dir/profiles.json}"
skills_file="${NIDAVELIR_SKILLS_LOCK_FILE:-$script_dir/skills.lock.json}"
base_instruction_budget="${NIDAVELIR_BASE_PROMPT_MAX_BYTES:-1200}"
profile_instruction_budget="${NIDAVELIR_PROFILE_PROMPT_MAX_BYTES:-1800}"

fail() {
  printf 'profile catalog validation failed: %s\n' "$1" >&2
  exit 1
}

jq -e '.schema_version | type == "number" and . > 0 and floor == .' "$profiles_file" >/dev/null \
  || fail "schema_version must be a positive integer"

jq -e '.base_skills | type == "array" and index("ponytail") != null' "$profiles_file" >/dev/null \
  || fail "ponytail must remain in base_skills"

required_profiles=(
  generic
  frontend-web
  backend
  fullstack
  devops
  qa
  database
  android-xml
  android-compose
  design
  docs
)

for profile in "${required_profiles[@]}"; do
  jq -e --arg profile "$profile" '.profiles[$profile] != null' "$profiles_file" >/dev/null \
    || fail "missing required profile: $profile"
done

base_bytes="$(jq -r '.base_instructions' "$profiles_file" | wc -c | tr -d ' ')"
(( base_bytes <= base_instruction_budget )) \
  || fail "base_instructions is ${base_bytes} bytes; budget is ${base_instruction_budget}"

while IFS=$'\t' read -r profile instruction; do
  bytes="$(printf '%s' "$instruction" | wc -c | tr -d ' ')"
  (( bytes <= profile_instruction_budget )) \
    || fail "profile $profile instructions are ${bytes} bytes; budget is ${profile_instruction_budget}"
  (( bytes >= 80 )) \
    || fail "profile $profile instructions are suspiciously short (${bytes} bytes)"
done < <(jq -r '.profiles | to_entries[] | [.key, .value.instructions] | @tsv' "$profiles_file")

known_skills="$(jq -r '.skills[].id' "$skills_file" | sort -u)"
while IFS= read -r skill; do
  [[ -n "$skill" ]] || continue
  grep -Fxq "$skill" <<<"$known_skills" || fail "profile references unknown skill: $skill"
done < <(jq -r '[.base_skills[], (.profiles[].skills[]?)] | unique[]' "$profiles_file")

printf 'profile catalog OK: %s profiles, base=%sB, per-profile budget=%sB\n' \
  "$(jq '.profiles | length' "$profiles_file")" \
  "$base_bytes" \
  "$profile_instruction_budget"
