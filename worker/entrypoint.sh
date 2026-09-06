#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"

if [[ ! -d "$workspace" ]]; then
  echo "nidavelir-worker: workspace does not exist: $workspace" >&2
  exit 64
fi

cd "$workspace"
exec "$@"
