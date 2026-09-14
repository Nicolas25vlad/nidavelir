#!/usr/bin/env bash
set -euo pipefail

script="$(dirname "$0")/detect-validation.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

repo="$work/repo"
mkdir -p "$repo"
cat > "$repo/.nidavelir.json" <<'JSON'
{
  "validation_commands": [
    {
      "name": "repo tests",
      "type": "test",
      "command": "pytest -q",
      "timeout_seconds": 120
    }
  ]
}
JSON
repo_plan="$(NIDAVELIR_WORKSPACE="$repo" "$script")"
test "$(jq -r '.mode' <<<"$repo_plan")" = "repo"
test "$(jq -r '.commands[0].command' <<<"$repo_plan")" = "pytest -q"
test "$(jq -r '.commands[0].timeout_seconds' <<<"$repo_plan")" = "120"

bad="$work/bad"
mkdir -p "$bad"
printf '%s\n' '{"validation_commands":[{"name":"oops","type":"shell","command":"true"}]}' > "$bad/.nidavelir.json"
bad_plan="$(NIDAVELIR_WORKSPACE="$bad" "$script")"
test "$(jq -r '.mode' <<<"$bad_plan")" = "skipped"
jq -e '.reason | contains("invalid .nidavelir.json")' <<<"$bad_plan" >/dev/null

auto="$work/auto"
mkdir -p "$auto"
printf '%s\n' '{"scripts":{"build":"echo built"}}' > "$auto/package.json"
auto_plan="$(NIDAVELIR_WORKSPACE="$auto" "$script")"
test "$(jq -r '.mode' <<<"$auto_plan")" = "auto"
jq -e '.commands[0].command | contains("npm run build")' <<<"$auto_plan" >/dev/null
