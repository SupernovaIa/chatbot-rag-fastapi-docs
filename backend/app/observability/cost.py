"""Gemini cost estimation per query.

Prices are per **million tokens** in USD, sourced from the Google AI Studio
pricing page.  Because this project runs on the free tier (zero-cost), these
values are informational — they let you measure the economic impact of
architecture decisions (caching, shorter prompts, batch calls) before
promoting to a paid tier.

Pricing anchored: 2026-05-20
Source: https://ai.google.dev/pricing  (Gemini API, May 2026)
Model IDs mirror those in ``app.config.Settings`` (ADR-001).

Usage
-----
>>> from app.chat.models import UsageMeta
>>> from app.observability.cost import compute_cost
>>> usage = UsageMeta(prompt_token_count=1500, cached_content_token_count=1200,
...                   candidates_token_count=300, total_token_count=1800)
>>> cost = compute_cost(usage, "gemini-3.5-flash")
>>> cost.total_usd  # will reflect ~1500 input - 1200 cached + 1200 cached_rate + 300 output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.chat.models import UsageMeta

# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------

# Structure: model_id → {"input": $/M, "cached_input": $/M, "output": $/M}
# Pricing anchored 2026-05-20.  Update when Google changes rates.
_PRICING: dict[str, dict[str, float]] = {
    # Gemini 3.5 Flash — generation, reranker, rewriter (ADR-001, anchored 2026-05-20)
    "gemini-3.5-flash": {
        "input": 0.30,          # $ per 1M non-cached input tokens
        "cached_input": 0.075,  # $ per 1M cached input tokens (75 % discount)
        "output": 1.25,         # $ per 1M output tokens
    },
    # Gemini 3 Pro — evals judge only (ADR-007, anchored 2026-05-24)
    "gemini-3-pro-preview": {
        "input": 1.25,
        "cached_input": 0.3125,
        "output": 5.00,
    },
    # Gemini 3 Pro stable alias (same pricing)
    "gemini-3-pro": {
        "input": 1.25,
        "cached_input": 0.3125,
        "output": 5.00,
    },
}

# Default fallback when a model is not in the table (use Flash pricing)
_DEFAULT_MODEL = "gemini-3.5-flash"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class QueryCost:
    """Estimated cost breakdown for a single Gemini call.

    All monetary values are in USD.  ``caching_available`` is True when the
    API reported at least one cached token; False when the field was absent or
    zero (see Issue #12 — implicit caching behaviour in streaming mode).
    """

    model: str
    # Token counts (raw from UsageMeta)
    prompt_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    # Derived: non-cached input = prompt_tokens - cached_tokens
    non_cached_input_tokens: int = field(init=False)
    # Cost breakdown
    input_usd: float = field(init=False)    # non-cached input cost
    cached_usd: float = field(init=False)   # cached input cost
    output_usd: float = field(init=False)   # output cost
    total_usd: float = field(init=False)
    caching_available: bool = field(init=False)

    def __post_init__(self) -> None:
        rates = _PRICING.get(self.model, _PRICING[_DEFAULT_MODEL])

        # Defensive: cached cannot exceed total prompt
        cached = max(0, min(self.cached_tokens, self.prompt_tokens))
        non_cached = max(0, self.prompt_tokens - cached)

        self.non_cached_input_tokens = non_cached
        self.caching_available = cached > 0

        _M = 1_000_000.0  # tokens per pricing unit
        self.input_usd = non_cached / _M * rates["input"]
        self.cached_usd = cached / _M * rates["cached_input"]
        self.output_usd = self.output_tokens / _M * rates["output"]
        self.total_usd = self.input_usd + self.cached_usd + self.output_usd

    @property
    def savings_usd(self) -> float:
        """USD saved by implicit caching vs. billing all tokens at full price."""
        if not self.caching_available:
            return 0.0
        rates = _PRICING.get(self.model, _PRICING[_DEFAULT_MODEL])
        full_price = self.cached_tokens / 1_000_000.0 * rates["input"]
        actual_price = self.cached_usd
        return max(0.0, full_price - actual_price)

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of input tokens that were served from cache (0-1)."""
        if self.prompt_tokens == 0:
            return 0.0
        return max(0.0, min(1.0, self.cached_tokens / self.prompt_tokens))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_cost(
    usage: "UsageMeta",
    model: str,
    *,
    override_cached_tokens: Optional[int] = None,
) -> QueryCost:
    """Compute the estimated USD cost for *usage* on the given *model*.

    Parameters
    ----------
    usage:
        ``UsageMeta`` instance from ``app.chat.models``.
    model:
        Gemini model ID (e.g. ``"gemini-3.5-flash"``).
    override_cached_tokens:
        Pass an explicit cached-token count if the API did not report one
        (useful when LangChain streaming omits ``cached_content_token_count``).
    """
    cached = (
        override_cached_tokens
        if override_cached_tokens is not None
        else (usage.cached_content_token_count or 0)
    )
    return QueryCost(
        model=model,
        prompt_tokens=usage.prompt_token_count or 0,
        cached_tokens=cached,
        output_tokens=usage.candidates_token_count or 0,
    )


def list_known_models() -> list[str]:
    """Return the list of model IDs with known pricing."""
    return list(_PRICING.keys())


def pricing_for_model(model: str) -> dict[str, float]:
    """Return the pricing dict for *model* (falls back to Flash rates)."""
    return dict(_PRICING.get(model, _PRICING[_DEFAULT_MODEL]))
