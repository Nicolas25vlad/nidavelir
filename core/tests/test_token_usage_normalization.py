from types import SimpleNamespace

import pytest

from nidavelir_core.execution.repository import _apply_token_usage


def _attempt():
    return SimpleNamespace(
        input_tokens=None,
        cached_input_tokens=None,
        cache_write_input_tokens=None,
        output_tokens=None,
        reasoning_tokens=None,
        total_tokens=None,
        cache_hit_ratio=None,
        model=None,
    )


def test_explicit_unknown_total_is_not_inferred_from_partial_usage() -> None:
    attempt = _attempt()

    _apply_token_usage(
        attempt,
        {
            "input_tokens": 12,
            "cached_input_tokens": None,
            "cache_write_input_tokens": None,
            "output_tokens": 4,
            "total_tokens": None,
        },
    )

    assert attempt.input_tokens == 12
    assert attempt.output_tokens == 4
    assert attempt.total_tokens is None
    assert attempt.cache_hit_ratio is None


def test_legacy_payload_without_total_keeps_backwards_compatible_inference() -> None:
    attempt = _attempt()

    _apply_token_usage(attempt, {"input_tokens": 12, "output_tokens": 4})

    assert attempt.total_tokens == 16


def test_normalized_cursor_input_produces_meaningful_cache_hit_ratio() -> None:
    attempt = _attempt()

    _apply_token_usage(
        attempt,
        {
            "input_tokens": 440,
            "cached_input_tokens": 300,
            "cache_write_input_tokens": 20,
            "output_tokens": 40,
            "total_tokens": 480,
        },
    )

    assert attempt.total_tokens == 480
    assert attempt.cache_hit_ratio == pytest.approx(300 / 440)
