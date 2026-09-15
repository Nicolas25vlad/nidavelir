#!/usr/bin/env bash
set -euo pipefail

parser="/usr/local/lib/nidavelir-worker/extract-cursor-usage.sh"

full="$(mktemp)"
partial="$(mktemp)"
missing="$(mktemp)"
trap 'rm -f "$full" "$partial" "$missing"' EXIT

cat >"$full" <<'JSON'
{"result":"done","usage":{"inputTokens":120,"outputTokens":40,"cacheReadTokens":300,"cacheWriteTokens":20,"reasoningTokens":10,"totalTokens":490}}
JSON
normalized="$("$parser" "$full")"
test "$(jq -r '.input_tokens' <<<"$normalized")" = "120"
test "$(jq -r '.cached_input_tokens' <<<"$normalized")" = "300"
test "$(jq -r '.cache_write_input_tokens' <<<"$normalized")" = "20"
test "$(jq -r '.output_tokens' <<<"$normalized")" = "40"
test "$(jq -r '.reasoning_output_tokens' <<<"$normalized")" = "10"
test "$(jq -r '.total_tokens' <<<"$normalized")" = "490"

cat >"$partial" <<'JSON'
{"usage":{"inputTokens":12,"outputTokens":4}}
JSON
normalized="$("$parser" "$partial")"
test "$(jq -r '.input_tokens' <<<"$normalized")" = "12"
test "$(jq -r '.output_tokens' <<<"$normalized")" = "4"
test "$(jq -r '.cached_input_tokens' <<<"$normalized")" = "null"
test "$(jq -r '.total_tokens' <<<"$normalized")" = "null"

printf '%s\n' '{"result":"done"}' >"$missing"
test "$("$parser" "$missing")" = "null"
