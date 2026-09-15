#!/usr/bin/env bash
set -euo pipefail

parser="/usr/local/lib/nidavelir-worker/extract-cursor-usage.sh"

full="$(mktemp)"
computed="$(mktemp)"
partial="$(mktemp)"
missing="$(mktemp)"
trap 'rm -f "$full" "$computed" "$partial" "$missing"' EXIT

cat >"$full" <<'JSON'
{"result":"done","usage":{"inputTokens":120,"outputTokens":40,"cacheReadTokens":300,"cacheWriteTokens":20,"reasoningTokens":10,"totalTokens":480}}
JSON
normalized="$("$parser" "$full")"
test "$(jq -r '.input_tokens' <<<"$normalized")" = "440"
test "$(jq -r '.cached_input_tokens' <<<"$normalized")" = "300"
test "$(jq -r '.cache_write_input_tokens' <<<"$normalized")" = "20"
test "$(jq -r '.output_tokens' <<<"$normalized")" = "40"
test "$(jq -r '.reasoning_output_tokens' <<<"$normalized")" = "10"
test "$(jq -r '.total_tokens' <<<"$normalized")" = "480"

cat >"$computed" <<'JSON'
{"usage":{"inputTokens":12,"outputTokens":4,"cacheReadTokens":30,"cacheWriteTokens":2}}
JSON
normalized="$("$parser" "$computed")"
test "$(jq -r '.input_tokens' <<<"$normalized")" = "44"
test "$(jq -r '.cached_input_tokens' <<<"$normalized")" = "30"
test "$(jq -r '.cache_write_input_tokens' <<<"$normalized")" = "2"
test "$(jq -r '.total_tokens' <<<"$normalized")" = "48"

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
