#!/usr/bin/env bash
set -euo pipefail

profiles_file="${NIDAVELIR_PROFILES_FILE:-/usr/local/lib/nidavelir-worker/profiles.json}"
store="${NIDAVELIR_SKILL_STORE:-/opt/nidavelir/skill-store}"
task_json="${NIDAVELIR_TASK_JSON:?NIDAVELIR_TASK_JSON is required}"
workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"

explicit="$(jq -r '.profile // "auto"' <<<"$task_json" | tr '[:upper:]' '[:lower:]')"
text="$(jq -r '[.title, .description, (.acceptance_criteria // [] | join(" "))] | join(" ") | ascii_downcase' <<<"$task_json")"

has_profile() {
  jq -e --arg profile "$1" '.profiles[$profile] != null' "$profiles_file" >/dev/null
}

repo_has() {
  find "$workspace" -maxdepth 4 -type f \( "$@" \) -print -quit 2>/dev/null | grep -q .
}

repo_mentions() {
  local pattern="$1"
  shift
  grep -Eiq "$pattern" "$@" 2>/dev/null
}

score_frontend=0
score_backend=0
score_infra=0
score_testing=0
score_database=0
score_android=0
score_docs=0

[[ "$text" =~ frontend|react|typescript|tsx|css|ui|ux|vite|next\.js|nextjs ]] && score_frontend=$((score_frontend + 3))
repo_has -name 'package.json' -o -name '*.tsx' -o -name '*.jsx' && score_frontend=$((score_frontend + 2))

[[ "$text" =~ backend|api|endpoint|fastapi|server|service|spring ]] && score_backend=$((score_backend + 3))
repo_has -name 'pyproject.toml' -o -name 'pom.xml' -o -name 'build.gradle' -o -name 'build.gradle.kts' && score_backend=$((score_backend + 1))

[[ "$text" =~ docker|docker[[:space:]]compose|kubernetes|k8s|infra|devops|pipeline|ci/cd|github[[:space:]]actions ]] && score_infra=$((score_infra + 4))
repo_has -name 'Dockerfile' -o -name 'compose.yaml' -o -name 'compose.yml' -o -name '*.tf' && score_infra=$((score_infra + 2))

[[ "$text" =~ test|testing|qa|pytest|vitest|playwright|e2e ]] && score_testing=$((score_testing + 4))
[[ "$text" =~ postgres|postgresql|database|sql|migration|schema|index ]] && score_database=$((score_database + 4))
repo_has -name '*.sql' -o -path '*/migrations/*' && score_database=$((score_database + 1))

[[ "$text" =~ android|kotlin|jetpack|compose[[:space:]]ui|gradle ]] && score_android=$((score_android + 4))
repo_has -name 'AndroidManifest.xml' && score_android=$((score_android + 4))

[[ "$text" =~ readme|documentation|docs|markdown ]] && score_docs=$((score_docs + 3))

if [[ "$explicit" != "auto" ]]; then
  has_profile "$explicit" || { printf 'unknown agent profile: %s\n' "$explicit" >&2; exit 64; }
  profile="$explicit"
elif (( score_frontend >= 3 && score_backend >= 3 )); then
  profile="fullstack"
else
  profile="generic"
  best=0
  for candidate in frontend backend infra testing database android docs; do
    score_var="score_${candidate}"
    score="${!score_var}"
    if (( score > best )); then
      best="$score"
      profile="$candidate"
    fi
  done
fi

base_skills="$(jq -r '.base_skills[]' "$profiles_file")"
profile_skills="$(jq -r --arg profile "$profile" '.profiles[$profile].skills[]' "$profiles_file")"
extra_skills=""

add_extra_skill() {
  extra_skills+="$1"$'\n'
}

case "$profile" in
  frontend|fullstack)
    [[ "$text" =~ architecture|refactor|feature[[:space:]]structure|component[[:space:]]structure ]] && add_extra_skill feature-arch
    [[ "$text" =~ vitest|unit[[:space:]]test|frontend[[:space:]]test ]] && add_extra_skill vitest
    ;;
  testing)
    [[ "$text" =~ playwright|e2e|browser ]] && add_extra_skill playwright
    [[ "$text" =~ vitest|frontend|react|typescript ]] && add_extra_skill vitest
    ;;
esac

if [[ "$profile" == "backend" || "$profile" == "fullstack" ]]; then
  if [[ "$text" =~ fastapi ]] || repo_mentions 'fastapi' "$workspace/pyproject.toml" "$workspace/requirements.txt" "$workspace/requirements-dev.txt"; then
    add_extra_skill fastapi
  fi
  (( score_database >= 4 )) && add_extra_skill postgres
fi

if [[ "$profile" == "infra" ]]; then
  if [[ "$text" =~ docker[[:space:]]compose|compose\.ya?ml ]] || repo_has -name 'compose.yaml' -o -name 'compose.yml'; then
    add_extra_skill docker-compose
  fi
  if [[ "$text" =~ kubernetes|k8s|helm ]] || repo_has -name 'kustomization.yaml' -o -name 'Chart.yaml'; then
    add_extra_skill kubernetes
  fi
fi

if [[ "$profile" == "android" ]]; then
  [[ "$text" =~ test|testing|instrumentation ]] && add_extra_skill android-testing
  [[ "$text" =~ edge-to-edge|edge[[:space:]]to[[:space:]]edge|system[[:space:]]bar|inset ]] && add_extra_skill android-edge-to-edge
fi

skills="$(printf '%s\n%s\n%s' "$base_skills" "$profile_skills" "$extra_skills" | sed '/^$/d' | awk '!seen[$0]++')"

rm -rf "$HOME/.agents/skills" "$HOME/.codex/skills"
mkdir -p "$HOME/.agents/skills" "$HOME/.codex/skills"
while IFS= read -r skill; do
  [[ -n "$skill" ]] || continue
  [[ -f "$store/$skill/SKILL.md" ]] || { printf 'missing bundled skill: %s\n' "$skill" >&2; exit 65; }
  ln -s "$store/$skill" "$HOME/.agents/skills/$skill"
  ln -s "$store/$skill" "$HOME/.codex/skills/$skill"
done <<<"$skills"

instructions="$(jq -r --arg profile "$profile" '.profiles[$profile].instructions' "$profiles_file")"
skills_csv="$(paste -sd, <<<"$skills")"

jq -cn --arg profile "$profile" --arg instructions "$instructions" --arg skills "$skills_csv" '{profile:$profile,instructions:$instructions,skills:($skills|split(",")|map(select(length>0)))}'
