"""Tests for backend/app/observability/cost.py.

Covers: QueryCost dataclass, compute_cost(), edge cases (zero tokens, no
caching, full caching, unknown model), and pricing arithmetic.
"""

from __future__ import annotations

import pytest

from app.chat.models import UsageMeta
from app.observability.cost import (
    QueryCost,
    compute_cost,
    list_known_models,
    pricing_for_model,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLASH = "gemini-3.5-flash"
_PRO = "gemini-3-pro-preview"
_UNKNOWN = "gemini-99-ultra"  # not in pricing table → falls back to Flash


def _usage(prompt: int = 0, cached: int = 0, output: int = 0) -> UsageMeta:
    return UsageMeta(
        prompt_token_count=prompt,
        cached_content_token_count=cached,
        candidates_token_count=output,
        total_token_count=prompt + output,
    )


# ---------------------------------------------------------------------------
# QueryCost — basic arithmetic
# ---------------------------------------------------------------------------


class TestQueryCostArithmetic:
    def test_zero_tokens_all_costs_zero(self) -> None:
        cost = QueryCost(model=_FLASH, prompt_tokens=0, cached_tokens=0, output_tokens=0)
        assert cost.input_usd == 0.0
        assert cost.cached_usd == 0.0
        assert cost.output_usd == 0.0
        assert cost.total_usd == 0.0

    def test_no_caching(self) -> None:
        # 1 000 input, 0 cached, 200 output with Flash rates
        cost = QueryCost(model=_FLASH, prompt_tokens=1_000, cached_tokens=0, output_tokens=200)
        # input_usd = 1000 / 1e6 * 0.30 = 0.0003
        assert pytest.approx(cost.input_usd, rel=1e-6) == 1_000 / 1e6 * 0.30
        assert cost.cached_usd == 0.0
        # output_usd = 200 / 1e6 * 1.25 = 0.00025
        assert pytest.approx(cost.output_usd, rel=1e-6) == 200 / 1e6 * 1.25
        expected_total = 1_000 / 1e6 * 0.30 + 200 / 1e6 * 1.25
        assert pytest.approx(cost.total_usd, rel=1e-6) == expected_total

    def test_with_caching(self) -> None:
        # 2 000 prompt, 1 200 cached → 800 non-cached
        cost = QueryCost(model=_FLASH, prompt_tokens=2_000, cached_tokens=1_200, output_tokens=300)
        assert cost.non_cached_input_tokens == 800
        expected_input = 800 / 1e6 * 0.30
        expected_cached = 1_200 / 1e6 * 0.075
        expected_output = 300 / 1e6 * 1.25
        assert pytest.approx(cost.input_usd, rel=1e-6) == expected_input
        assert pytest.approx(cost.cached_usd, rel=1e-6) == expected_cached
        assert pytest.approx(cost.output_usd, rel=1e-6) == expected_output
        assert pytest.approx(cost.total_usd, rel=1e-6) == (
            expected_input + expected_cached + expected_output
        )

    def test_caching_available_flag(self) -> None:
        no_cache = QueryCost(model=_FLASH, prompt_tokens=1_000, cached_tokens=0, output_tokens=0)
        with_cache = QueryCost(model=_FLASH, prompt_tokens=1_000, cached_tokens=500, output_tokens=0)
        assert not no_cache.caching_available
        assert with_cache.caching_available

    def test_cache_hit_rate(self) -> None:
        cost = QueryCost(model=_FLASH, prompt_tokens=2_000, cached_tokens=1_200, output_tokens=0)
        assert pytest.approx(cost.cache_hit_rate, rel=1e-4) == 1_200 / 2_000

    def test_cache_hit_rate_zero_prompt(self) -> None:
        cost = QueryCost(model=_FLASH, prompt_tokens=0, cached_tokens=0, output_tokens=100)
        assert cost.cache_hit_rate == 0.0

    def test_savings_usd(self) -> None:
        # 1 200 cached tokens: paying cached rate vs full input rate
        cached_tokens = 1_200
        cost = QueryCost(model=_FLASH, prompt_tokens=2_000, cached_tokens=cached_tokens, output_tokens=300)
        full_price = cached_tokens / 1e6 * 0.30
        actual_price = cached_tokens / 1e6 * 0.075
        expected_savings = full_price - actual_price
        assert pytest.approx(cost.savings_usd, rel=1e-6) == expected_savings

    def test_savings_zero_without_caching(self) -> None:
        cost = QueryCost(model=_FLASH, prompt_tokens=1_000, cached_tokens=0, output_tokens=200)
        assert cost.savings_usd == 0.0

    def test_cached_cannot_exceed_prompt(self) -> None:
        # cached > prompt — should be clamped to prompt
        cost = QueryCost(model=_FLASH, prompt_tokens=500, cached_tokens=1_000, output_tokens=0)
        assert cost.non_cached_input_tokens == 0
        assert cost.cached_tokens == 1_000  # stored as-is
        # But the effective cached in the calculation is clamped
        assert cost.input_usd == 0.0
        assert cost.cached_usd == pytest.approx(500 / 1e6 * 0.075)


# ---------------------------------------------------------------------------
# Pro model pricing
# ---------------------------------------------------------------------------


class TestProModelPricing:
    def test_pro_rates_higher_than_flash(self) -> None:
        usage = _usage(prompt=1_000, output=100)
        flash_cost = compute_cost(usage, _FLASH)
        pro_cost = compute_cost(usage, _PRO)
        assert pro_cost.total_usd > flash_cost.total_usd

    def test_pro_specific_values(self) -> None:
        cost = QueryCost(model=_PRO, prompt_tokens=1_000, cached_tokens=0, output_tokens=100)
        assert pytest.approx(cost.input_usd, rel=1e-6) == 1_000 / 1e6 * 1.25
        assert pytest.approx(cost.output_usd, rel=1e-6) == 100 / 1e6 * 5.00


# ---------------------------------------------------------------------------
# Unknown model fallback
# ---------------------------------------------------------------------------


class TestUnknownModelFallback:
    def test_unknown_model_falls_back_to_flash(self) -> None:
        cost_unknown = QueryCost(model=_UNKNOWN, prompt_tokens=1_000, cached_tokens=0, output_tokens=100)
        cost_flash = QueryCost(model=_FLASH, prompt_tokens=1_000, cached_tokens=0, output_tokens=100)
        assert pytest.approx(cost_unknown.total_usd, rel=1e-9) == cost_flash.total_usd


# ---------------------------------------------------------------------------
# compute_cost() public API
# ---------------------------------------------------------------------------


class TestComputeCost:
    def test_from_usage_meta_no_caching(self) -> None:
        usage = _usage(prompt=2_500, cached=0, output=300)
        cost = compute_cost(usage, _FLASH)
        assert cost.model == _FLASH
        assert cost.prompt_tokens == 2_500
        assert cost.cached_tokens == 0
        assert cost.output_tokens == 300
        assert not cost.caching_available

    def test_from_usage_meta_with_caching(self) -> None:
        usage = _usage(prompt=2_500, cached=1_200, output=300)
        cost = compute_cost(usage, _FLASH)
        assert cost.caching_available
        assert cost.cached_tokens == 1_200
        assert cost.total_usd > 0

    def test_none_cached_treated_as_zero(self) -> None:
        # LangChain streaming may return None for cached_content_token_count
        usage = UsageMeta(
            prompt_token_count=1_000,
            cached_content_token_count=0,  # UsageMeta default is 0
            candidates_token_count=200,
            total_token_count=1_200,
        )
        cost = compute_cost(usage, _FLASH)
        assert cost.cached_tokens == 0
        assert not cost.caching_available

    def test_override_cached_tokens(self) -> None:
        usage = _usage(prompt=2_500, cached=0, output=300)
        cost_no_override = compute_cost(usage, _FLASH)
        cost_override = compute_cost(usage, _FLASH, override_cached_tokens=1_200)
        assert cost_override.total_usd < cost_no_override.total_usd
        assert cost_override.caching_available

    def test_returns_query_cost_instance(self) -> None:
        usage = _usage(prompt=100, output=50)
        cost = compute_cost(usage, _FLASH)
        assert isinstance(cost, QueryCost)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestUtilityFunctions:
    def test_list_known_models_returns_list(self) -> None:
        models = list_known_models()
        assert isinstance(models, list)
        assert _FLASH in models
        assert _PRO in models

    def test_pricing_for_model_flash(self) -> None:
        rates = pricing_for_model(_FLASH)
        assert "input" in rates
        assert "cached_input" in rates
        assert "output" in rates
        assert rates["cached_input"] < rates["input"]  # caching is cheaper

    def test_pricing_for_unknown_falls_back(self) -> None:
        rates_unknown = pricing_for_model(_UNKNOWN)
        rates_flash = pricing_for_model(_FLASH)
        assert rates_unknown == rates_flash

    def test_cached_rate_is_75_pct_discount(self) -> None:
        """Cached input should cost 25% of full input (75% discount)."""
        rates = pricing_for_model(_FLASH)
        expected_cached = rates["input"] * 0.25
        assert pytest.approx(rates["cached_input"], rel=1e-6) == expected_cached


# ---------------------------------------------------------------------------
# Realistic example: typical RAG turn
# ---------------------------------------------------------------------------


class TestRealisticTurn:
    def test_typical_turn_cost_order_of_magnitude(self) -> None:
        """A typical RAG turn should cost roughly $0.001–$0.003."""
        usage = _usage(prompt=2_500, cached=1_200, output=300)
        cost = compute_cost(usage, _FLASH)
        # Sanity: not free, not expensive
        assert cost.total_usd > 0
        assert cost.total_usd < 0.01  # less than 1 cent

    def test_cached_turn_cheaper_than_uncached(self) -> None:
        cached = compute_cost(_usage(prompt=2_500, cached=1_200, output=300), _FLASH)
        uncached = compute_cost(_usage(prompt=2_500, cached=0, output=300), _FLASH)
        assert cached.total_usd < uncached.total_usd
