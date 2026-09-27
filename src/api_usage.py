from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Standard API pricing per 1M tokens.
#
# Keep this deliberately explicit rather than silently guessing prices for
# unknown models. If we use a model not listed here, token usage will still
# be reported but estimated cost will show as unavailable.
MODEL_PRICING = {
    "gpt-5.6-luna": {
        "input": 0.20,
        "cached_input": 0.02,
        "cache_write": 0.25,
        "output": 1.20,
    },

    "gpt-6-luna": {
        "input": 0.10,
        "cached_input": 0.01,
        "cache_write": 0.125,
        "output": 0.50,
    },

    "gpt-5.5": {
        "input": 5.00,
        "cached_input": 0.50,

        # GPT-5.5 does not have the separate 1.25x cache-write
        # pricing used by GPT-5.6+.
        "cache_write": 5.00,

        "output": 30.00,
    },
}


def _number(
    value: Any,
) -> int:

    if value is None:
        return 0

    return int(value)


def pricing_for_model(
    model: str,
):

    for base_model, pricing in (
        MODEL_PRICING.items()
    ):

        if model == base_model:
            return pricing

        # Also support dated snapshots such as:
        #
        # gpt-6-luna-2026-09-22
        #
        if model.startswith(
            base_model + "-20"
        ):
            return pricing

    return None


@dataclass
class ApiUsageTracker:

    requests: int = 0

    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0

    output_tokens: int = 0
    reasoning_tokens: int = 0

    total_tokens: int = 0

    estimated_cost_usd: float = 0.0

    priced_requests: int = 0

    models: set[str] = field(
        default_factory=set
    )

    unpriced_models: set[str] = field(
        default_factory=set
    )

    def add_response(
        self,
        response,
    ):
        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return

        model = str(
            getattr(
                response,
                "model",
                "unknown",
            )
        )

        self.models.add(
            model
        )

        self.requests += 1


        # ----------------------------------------------------
        # Raw usage
        # ----------------------------------------------------

        input_tokens = _number(
            getattr(
                usage,
                "input_tokens",
                0,
            )
        )

        output_tokens = _number(
            getattr(
                usage,
                "output_tokens",
                0,
            )
        )

        total_tokens = _number(
            getattr(
                usage,
                "total_tokens",
                0,
            )
        )


        input_details = getattr(
            usage,
            "input_tokens_details",
            None,
        )

        output_details = getattr(
            usage,
            "output_tokens_details",
            None,
        )


        cached_tokens = _number(
            getattr(
                input_details,
                "cached_tokens",
                0,
            )
        )

        cache_write_tokens = _number(
            getattr(
                input_details,
                "cache_write_tokens",
                0,
            )
        )

        reasoning_tokens = _number(
            getattr(
                output_details,
                "reasoning_tokens",
                0,
            )
        )


        self.input_tokens += (
            input_tokens
        )

        self.cached_input_tokens += (
            cached_tokens
        )

        self.cache_write_tokens += (
            cache_write_tokens
        )

        self.output_tokens += (
            output_tokens
        )

        self.reasoning_tokens += (
            reasoning_tokens
        )

        self.total_tokens += (
            total_tokens
        )


        # ----------------------------------------------------
        # Cost
        #
        # input_tokens includes all input categories.
        # Split it into ordinary / cached / cache-write.
        #
        # Output price already applies to reasoning tokens;
        # reasoning_tokens is a breakdown of output_tokens,
        # not an additional charge.
        # ----------------------------------------------------

        pricing = pricing_for_model(
            model
        )

        if pricing is None:

            self.unpriced_models.add(
                model
            )

            return


        ordinary_input_tokens = max(
            0,
            input_tokens
            - cached_tokens
            - cache_write_tokens,
        )


        input_cost = (
            ordinary_input_tokens
            * pricing["input"]
            / 1_000_000
        )

        cached_cost = (
            cached_tokens
            * pricing["cached_input"]
            / 1_000_000
        )

        cache_write_cost = (
            cache_write_tokens
            * pricing["cache_write"]
            / 1_000_000
        )

        output_cost = (
            output_tokens
            * pricing["output"]
            / 1_000_000
        )


        self.estimated_cost_usd += (
            input_cost
            + cached_cost
            + cache_write_cost
            + output_cost
        )

        self.priced_requests += 1


    @property
    def ordinary_input_tokens(
        self,
    ):

        return max(
            0,
            self.input_tokens
            - self.cached_input_tokens
            - self.cache_write_tokens,
        )


    @property
    def cost_available(
        self,
    ):

        return (
            self.requests > 0
            and self.priced_requests
            == self.requests
        )


    def cost_text(
        self,
    ):

        if not self.cost_available:
            return "unavailable"

        # Six decimals is useful because Luna requests can be
        # substantially below one cent.
        return (
            f"${self.estimated_cost_usd:.6f}"
        )
