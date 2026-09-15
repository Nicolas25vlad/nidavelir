#!/usr/bin/env bash
set -euo pipefail

input="${1:-/dev/stdin}"

jq -c '
  def nonnegative_number($value):
    if ($value | type) == "number" and $value >= 0 then $value else null end;

  (.usage // .tokenUsage // .token_usage // null) as $usage
  | if $usage == null then
      null
    else
      nonnegative_number($usage.inputTokens // $usage.input_tokens // null) as $uncached_input
      | nonnegative_number(
          $usage.cacheReadTokens
          // $usage.cachedInputTokens
          // $usage.cache_read_tokens
          // $usage.cached_input_tokens
          // null
        ) as $cache_read
      | nonnegative_number(
          $usage.cacheWriteTokens
          // $usage.cache_write_tokens
          // $usage.cache_write_input_tokens
          // null
        ) as $cache_write
      | nonnegative_number($usage.outputTokens // $usage.output_tokens // null) as $output
      | nonnegative_number(
          $usage.reasoningTokens
          // $usage.thoughtTokens
          // $usage.reasoning_tokens
          // $usage.reasoning_output_tokens
          // null
        ) as $reasoning
      | nonnegative_number($usage.totalTokens // $usage.total_tokens // null) as $reported_total
      | (
          if $uncached_input != null and $cache_read != null and $cache_write != null then
            $uncached_input + $cache_read + $cache_write
          else
            $uncached_input
          end
        ) as $normalized_input
      | (
          if $reported_total != null then
            $reported_total
          elif $uncached_input != null and $cache_read != null and $cache_write != null and $output != null then
            $uncached_input + $cache_read + $cache_write + $output
          else
            null
          end
        ) as $total
      | {
          input_tokens: $normalized_input,
          cached_input_tokens: $cache_read,
          cache_write_input_tokens: $cache_write,
          output_tokens: $output,
          reasoning_output_tokens: $reasoning,
          total_tokens: $total
        }
      | if any(.[]; . != null) then . else null end
    end
' "$input" 2>/dev/null || printf 'null\n'
