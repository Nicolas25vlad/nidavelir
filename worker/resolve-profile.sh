#!/usr/bin/env bash
set -euo pipefail

profiles_file="${NIDAVELIR_PROFILES_FILE:-/usr/local/lib/nidavelir-worker/profiles.json}"
store="${NIDAVELIR_SKILL_STORE:-/opt/nidavelir/skill-store}"
task_json="${NIDAVELIR_TASK_JSON:?NIDAVELIR_TASK_JSON is required}"
workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"

explicit="$(jq -r '.profile // "auto"' <<<"$task_json" | tr '[:upper:]' '[:lower:]')"
text="$(jq -r '[.title, .description, (.acceptance_criteria // [] | join(" "))] | join(" ") | ascii_downcase' <<<"$task_json")"

normalize_profile() {
  case "$1" in
    frontend) printf '%s\n' 'frontend-web' ;;
    infra) printf '%s\n' 'devops' ;;
    testing) printf '%s\n' 'qa' ;;
    android) printf '%s\n' 'android-auto' ;;
    *) printf '%s\n' "$1" ;;
  esac
}

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

repo_contains() {
  local pattern="$1"
  shift
  find "$workspace" -maxdepth 5 -type f "$@" -print0 2>/dev/null \
    | xargs -0 -r grep -Eil -m1 "$pattern" 2>/dev/null \
    | grep -q .
}

score_frontend=0
score_backend=0
score_devops=0
score_qa=0
score_database=0
score_android=0
score_design=0
score_docs=0

[[ "$text" =~ frontend|react|typescript|tsx|css|vite|next\.js|nextjs|component|browser ]] && score_frontend=$((score_frontend + 3))
repo_has -name 'package.json' -o -name '*.tsx' -o -name '*.jsx' && score_frontend=$((score_frontend + 2))

[[ "$text" =~ backend|api|endpoint|fastapi|server|service|spring|controller|repository ]] && score_backend=$((score_backend + 3))
repo_has -name 'pyproject.toml' -o -name 'pom.xml' && score_backend=$((score_backend + 1))

[[ "$text" =~ docker|docker[[:space:]]compose|kubernetes|k8s|infra|devops|pipeline|ci/cd|github[[:space:]]actions|terraform|helm ]] && score_devops=$((score_devops + 4))
repo_has -name 'Dockerfile' -o -name 'compose.yaml' -o -name 'compose.yml' -o -name '*.tf' && score_devops=$((score_devops + 2))

[[ "$text" =~ test|testing|tests|qa|pytest|vitest|playwright|e2e|regression|flaky ]] && score_qa=$((score_qa + 4))
[[ "$text" =~ postgres|postgresql|database|sql|migration|schema|index|query ]] && score_database=$((score_database + 4))
repo_has -name '*.sql' -o -path '*/migrations/*' && score_database=$((score_database + 1))

[[ "$text" =~ android|kotlin|jetpack|compose[[:space:]]ui|xml[[:space:]]layout|fragment|activity|gradle ]] && score_android=$((score_android + 4))
repo_has -name 'AndroidManifest.xml' && score_android=$((score_android + 4))

[[ "$text" =~ design|ui|ux|wireframe|figma|design[[:space:]]system|typography|spacing|visual[[:space:]]hierarchy|responsive[[:space:]]layout|color[[:space:]]palette ]] && score_design=$((score_design + 4))
[[ "$text" =~ readme|documentation|docs|markdown ]] && score_docs=$((score_docs + 3))

android_profile() {
  if [[ "$text" =~ jetpack[[:space:]]compose|compose[[:space:]]ui|@composable|composable ]]; then
    printf '%s\n' 'android-compose'
    return
  fi
  if [[ "$text" =~ xml|viewbinding|databinding|fragment|recyclerview|constraintlayout ]]; then
    printf '%s\n' 'android-xml'
    return
  fi
  if repo_contains '@Composable|setContent[[:space:]]*\{' -name '*.kt'; then
    printf '%s\n' 'android-compose'
    return
  fi
  if repo_has -path '*/res/layout/*.xml' -o -path '*/res/layout-*/*.xml'; then
    printf '%s\n' 'android-xml'
    return
  fi
  printf '%s\n' 'android-xml'
}

normalized_explicit="$(normalize_profile "$explicit")"
if [[ "$normalized_explicit" != "auto" ]]; then
  if [[ "$normalized_explicit" == "android-auto" ]]; then
    profile="$(android_profile)"
  else
    has_profile "$normalized_explicit" || {
      printf 'unknown agent profile: %s\n' "$explicit" >&2
      exit 64
    }
    profile="$normalized_explicit"
  fi
elif (( score_android >= 4 )); then
  profile="$(android_profile)"
elif (( score_frontend >= 3 && score_backend >= 3 )); then
  profile="fullstack"
else
  profile="generic"
  best=0
  for candidate in design frontend backend devops qa database docs; do
    score_var="score_${candidate}"
    score="${!score_var}"
    if (( score > best )); then
      best="$score"
      case "$candidate" in
        frontend) profile="frontend-web" ;;
        *) profile="$candidate" ;;
      esac
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
  frontend-web|fullstack)
    [[ "$text" =~ architecture|refactor|feature[[:space:]]structure|component[[:space:]]structure ]] && add_extra_skill feature-arch
    [[ "$text" =~ vitest|unit[[:space:]]test|frontend[[:space:]]test ]] && add_extra_skill vitest
    ;;
  qa)
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

if [[ "$profile" == "devops" ]]; then
  if [[ "$text" =~ docker[[:space:]]compose|compose\.ya?ml ]] || repo_has -name 'compose.yaml' -o -name 'compose.yml'; then
    add_extra_skill docker-compose
  fi
  if [[ "$text" =~ kubernetes|k8s|helm ]] || repo_has -name 'kustomization.yaml' -o -name 'Chart.yaml'; then
    add_extra_skill kubernetes
  fi
fi

if [[ "$profile" == android-* ]]; then
  [[ "$text" =~ test|testing|instrumentation ]] && add_extra_skill android-testing
  [[ "$text" =~ edge-to-edge|edge[[:space:]]to[[:space:]]edge|system[[:space:]]bar|inset ]] && add_extra_skill android-edge-to-edge
fi

skills="$(printf '%s\n%s\n%s' "$base_skills" "$profile_skills" "$extra_skills" | sed '/^$/d' | awk '!seen[$0]++')"

rm -rf "$HOME/.agents/skills" "$HOME/.codex/skills"
mkdir -p "$HOME/.agents/skills" "$HOME/.codex/skills"
while IFS= read -r skill; do
  [[ -n "$skill" ]] || continue
  [[ -f "$store/$skill/SKILL.md" ]] || {
    printf 'missing bundled skill: %s\n' "$skill" >&2
    exit 65
  }
  ln -s "$store/$skill" "$HOME/.agents/skills/$skill"
  ln -s "$store/$skill" "$HOME/.codex/skills/$skill"
done <<<"$skills"

schema_version="$(jq -r '.schema_version' "$profiles_file")"
base_instructions="$(jq -r '.base_instructions' "$profiles_file")"
profile_instructions="$(jq -r --arg profile "$profile" '.profiles[$profile].instructions' "$profiles_file")"
instructions="${base_instructions} ${profile_instructions}"
prompt_fingerprint="$(printf '%s' "$instructions" | sha256sum | awk '{print $1}')"
skills_csv="$(paste -sd, <<<"$skills")"

jq -cn \
  --arg profile "$profile" \
  --arg instructions "$instructions" \
  --arg skills "$skills_csv" \
  --arg prompt_fingerprint "$prompt_fingerprint" \
  --argjson schema_version "$schema_version" \
  '{profile:$profile,schema_version:$schema_version,prompt_fingerprint:$prompt_fingerprint,instructions:$instructions,skills:($skills|split(",")|map(select(length>0)))}'
