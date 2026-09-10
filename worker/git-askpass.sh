#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  *Username*)
    printf '%s\n' "x-access-token"
    ;;
  *)
    printf '%s\n' "${NIDAVELIR_GITHUB_TOKEN:?NIDAVELIR_GITHUB_TOKEN is required}"
    ;;
esac
