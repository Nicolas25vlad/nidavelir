#!/usr/bin/env bash
set -euo pipefail

input="${1:-/dev/stdin}"

jq -c '
  (.usage // .tokenUsage // .token_usage // null) as $usage
  | if $usage == null then
      null
    else
      {
        input_tokens: ($usage.inputTokens // $usage.input_tokens // null),
        cached_input_tokens: (
          $usage.cacheReadTokens
          // $usage.cachedInputTokens
          // $usage.cache_read_tokens
          // $usage.cached_input_tokens
          // null
        ),
        cache_write_input_tokens: (
          $usage.cacheWriteTokens
          // $usage.cache_write_tokens
          // $usage.cache_write_input_tokens
          // null
        ),
        output_tokens: ($usage.outputTokens // $usage.output_tokens // null),
        reasoning_output_tokens: (
          $usage.reasoningTokens
          // $usage.thoughtTokens
          // $usage.reasoning_tokens
          // $usage.reasoning_output_tokens
          // null
        ),
        total_tokens: ($usage.totalTokens // $usage.total_tokens // null)
      }
      | if any(.[]; . != null) then . else null end
    end
' "$input" 2>/dev/null || printf 'null\n'
