#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
cd "$workspace"

commands='[]'
notes='[]'

append_note() {
  notes="$(jq -c --arg note "$1" '. + [$note]' <<<"$notes")"
}

append_command() {
  local name="$1"
  local type="$2"
  local command="$3"
  local timeout="$4"
  commands="$(jq -c \
    --arg name "$name" \
    --arg type "$type" \
    --arg command "$command" \
    --argjson timeout "$timeout" \
    '. + [{name:$name,type:$type,command:$command,timeout_seconds:$timeout}]' \
    <<<"$commands")"
}

# Inspect the root plus one directory level. This covers common monorepos without
# recursively walking vendor/build trees.
while IFS= read -r pyproject; do
  dir="$(dirname "$pyproject")"
  [[ "$dir" == "." ]] && dir_cmd="" || dir_cmd="cd ${dir#./} && "

  if ! command -v python3 >/dev/null 2>&1; then
    append_note "python project detected at ${dir#./}, but python3 is unavailable in this worker profile"
    continue
  fi

  if [[ -d "$dir/tests" ]] || grep -Eqi 'pytest' "$pyproject"; then
    install_target='.'
    if grep -Eq '^dev[[:space:]]*=' "$pyproject"; then
      install_target='.[dev]'
    fi
    command="${dir_cmd}python3 -m venv /tmp/nidavelir-validation-py && . /tmp/nidavelir-validation-py/bin/activate && python -m pip install -q -e '${install_target}' && python -m pip install -q pytest && python -m pytest -q"
    append_command "python tests (${dir#./})" "test" "$command" 900
  fi
done < <(find . -maxdepth 2 -name pyproject.toml -type f -print | sort)

while IFS= read -r package; do
  dir="$(dirname "$package")"
  [[ "$dir" == "." ]] && dir_cmd="" || dir_cmd="cd ${dir#./} && "

  has_build="$(jq -r '(.scripts.build // "") != ""' "$package" 2>/dev/null || printf 'false')"
  has_test="$(jq -r '(.scripts.test // "") != "" and ((.scripts.test // "") | contains("no test specified") | not)' "$package" 2>/dev/null || printf 'false')"

  node_steps=()
  if [[ -f "$dir/package-lock.json" ]]; then
    node_steps+=("npm ci --no-audit --no-fund")
  else
    node_steps+=("npm install --no-audit --no-fund")
  fi
  [[ "$has_test" == "true" ]] && node_steps+=("CI=1 npm test")
  [[ "$has_build" == "true" ]] && node_steps+=("npm run build")

  if (( ${#node_steps[@]} > 1 )); then
    command="${dir_cmd}$(IFS=' && '; echo "${node_steps[*]}")"
    type="test"
    [[ "$has_build" == "true" ]] && type="build"
    append_command "node validation (${dir#./})" "$type" "$command" 900
  fi
done < <(find . -maxdepth 2 -name package.json -type f -not -path '*/node_modules/*' -print | sort)

while IFS= read -r gradlew; do
  dir="$(dirname "$gradlew")"
  [[ "$dir" == "." ]] && dir_cmd="" || dir_cmd="cd ${dir#./} && "
  if [[ -x "$gradlew" ]]; then
    append_command "gradle tests (${dir#./})" "test" "${dir_cmd}./gradlew test --no-daemon" 1200
  else
    append_note "Gradle wrapper detected at ${dir#./}, but it is not executable"
  fi
done < <(find . -maxdepth 2 -name gradlew -type f -print | sort)

while IFS= read -r gomod; do
  dir="$(dirname "$gomod")"
  if command -v go >/dev/null 2>&1; then
    [[ "$dir" == "." ]] && dir_cmd="" || dir_cmd="cd ${dir#./} && "
    append_command "go tests (${dir#./})" "test" "${dir_cmd}go test ./..." 900
  else
    append_note "Go module detected at ${dir#./}, but Go is unavailable in this worker profile"
  fi
done < <(find . -maxdepth 2 -name go.mod -type f -print | sort)

count="$(jq 'length' <<<"$commands")"
if (( count > 0 )); then
  jq -cn --argjson commands "$commands" --argjson notes "$notes" \
    '{mode:"auto",reason:"safe checks auto-resolved from repository signals",commands:$commands,notes:$notes}'
else
  reason="no supported safe validation checks detected"
  if (( $(jq 'length' <<<"$notes") > 0 )); then
    reason+="; $(jq -r 'join("; ")' <<<"$notes")"
  fi
  jq -cn --arg reason "$reason" --argjson notes "$notes" \
    '{mode:"skipped",reason:$reason,commands:[],notes:$notes}'
fi
