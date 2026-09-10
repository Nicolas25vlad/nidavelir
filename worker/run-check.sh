#!/usr/bin/env bash
set -euo pipefail

workspace="${NIDAVELIR_WORKSPACE:-/workspace/repo}"
command="${NIDAVELIR_VALIDATION_COMMAND:?NIDAVELIR_VALIDATION_COMMAND is required}"

cd "$workspace"
exec bash -lc "$command"
