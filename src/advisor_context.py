from __future__ import annotations

from typing import Any

from world_state import WorldState


class AdvisorContext:
    """
    Builds compact, intentionally exposed context for the AI advisor.

    This layer is important:

        campaign.db / static_data.db
                 ↓
             WorldState
                 ↓
           AdvisorContext
                 ↓
               AI

    The AI should NOT receive arbitrary raw payload_json objects.
    """

    def __init__(
        self,
        db_path: str,
        static_db_path: str | None = None,
    ):
        self.world = WorldState(
            db_path,
            static_db_path,
        )

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _round(value):
        if isinstance(value, float):
            return round(value, 5)

        if isinstance(value, dict):
            return {
                key: AdvisorContext._round(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                AdvisorContext._round(item)
                for item in value
            ]

        return value

    @staticmethod
    def _effective_number(value):
        """
        EU5 often omits numeric values when they are effectively zero.

        Keep the original raw value in output, but this helper is useful
        for derived calculations.
        """

        if value is None:
            return 0.0

        return float(value)

    def _player_summary(self):
        player = self.world.get_player_country()

        if player is None:
            return None

        income = player.get("income")
        expense = player.get("expense")

        computed_balance = None

        if (
            income is not None
            and expense is not None
        ):
            computed_balance = (
                income - expense
            )

        return {
            "country_id": player.get(
                "country_id"
            ),
            "tag": player.get(
                "tag"
            ),
            "name": player.get(
                "name"
            ),
            "capital": player.get(
                "capital_name"
            ),
            "gold": player.get(
                "gold"
            ),
            "income": income,
            "expense": expense,

            # This is deliberately labelled "computed".
            # It is NOT EU5 balance_history_2.Gold.
            "computed_income_minus_expense":
                computed_balance,

            "population": player.get(
                "population"
            ),
            "great_power": bool(
                player.get(
                    "great_power"
                )
            ),
            "great_power_rank": player.get(
                "great_power_rank"
            ),
        }

    def _market_price_references(
        self,
        good: str,
        local_market_id: int,
        local_price: float | None,
        limit: int = 3,
    ):
        """
        Return cheaper visible market prices.

        IMPORTANT:
        These are PRICE REFERENCES, not automatically valid import
        opportunities. We do not yet model route reachability, trade
        costs, merchant capacity, or profitability here.
        """

        rows = self.world.get_good_worldwide(
            good
        )

        references = []

        for row in rows:

            if (
                row.get("market_id")
                == local_market_id
            ):
                continue

            price = row.get(
                "price"
            )

            if price is None:
                continue

            if (
                local_price is not None
                and price >= local_price
            ):
                continue

            references.append({
                "market_id": row.get(
                    "market_id"
                ),
                "market_name": row.get(
                    "market_name"
                ),
                "price": price,
                "supply": row.get(
                    "supply"
                ),
                "demand": row.get(
                    "demand"
                ),
                "surplus": row.get(
                    "surplus"
                ),
                "is_import": row.get(
                    "is_import"
                ),
                "is_export": row.get(
                    "is_export"
                ),
            })

            if len(references) >= limit:
                break

        return references

    # ========================================================
    # Market brief
    # ========================================================

    def market_brief(
        self,
        market_id: int,
        shortage_limit: int = 8,
        surplus_limit: int = 8,
        price_reference_limit: int = 3,
    ):
        campaign = (
            self.world.get_campaign_state()
        )

        player = self._player_summary()

        market = self.world.get_market(
            market_id
        )

        if market is None:
            raise ValueError(
                f"Market {market_id} not found"
            )

        shortages_raw = (
            self.world.get_market_shortages(
                market_id,
                limit=shortage_limit,
            )
        )

        surpluses_raw = (
            self.world.get_market_surpluses(
                market_id,
                limit=surplus_limit,
            )
        )

        shortages = []

        for row in shortages_raw:

            supply = self._effective_number(
                row.get("supply")
            )

            demand = self._effective_number(
                row.get("demand")
            )

            if demand > 0:
                coverage = supply / demand

                shortfall_share = (
                    max(
                        0.0,
                        demand - supply,
                    )
                    / demand
                )
            else:
                coverage = None
                shortfall_share = None

            local_price = row.get(
                "price"
            )

            shortages.append({
                "good": row.get(
                    "good"
                ),
                "name": row.get(
                    "good_name"
                ),
                "price": local_price,
                "supply": row.get(
                    "supply"
                ),
                "demand": row.get(
                    "demand"
                ),
                "balance": row.get(
                    "balance"
                ),
                "stockpile": row.get(
                    "stockpile"
                ),
                "supply_coverage": coverage,
                "shortfall_share": shortfall_share,

                # Preserve but do not overinterpret.
                "raw_trade_flags": {
                    "import": row.get(
                        "is_import"
                    ),
                    "export": row.get(
                        "is_export"
                    ),
                },

                "cheaper_visible_market_prices":
                    self._market_price_references(
                        row.get("good"),
                        market_id,
                        local_price,
                        limit=price_reference_limit,
                    ),
            })

        surpluses = []

        for row in surpluses_raw:

            surpluses.append({
                "good": row.get(
                    "good"
                ),
                "name": row.get(
                    "good_name"
                ),
                "price": row.get(
                    "price"
                ),
                "supply": row.get(
                    "supply"
                ),
                "demand": row.get(
                    "demand"
                ),
                "balance": row.get(
                    "balance"
                ),
                "stockpile": row.get(
                    "stockpile"
                ),
                "raw_trade_flags": {
                    "import": row.get(
                        "is_import"
                    ),
                    "export": row.get(
                        "is_export"
                    ),
                },
            })

        result = {
            "context_type": "eu5_market_brief",

            "as_of": {
                "game_date": (
                    campaign.get(
                        "game_date"
                    )
                    if campaign
                    else None
                ),
                "exact_snapshot": True,
            },

            "player": player,

            "market": {
                "market_id": market.get(
                    "market_id"
                ),
                "name": market.get(
                    "market_name"
                ),
                "center": market.get(
                    "center_name"
                ),
                "population": market.get(
                    "population"
                ),
                "capacity": market.get(
                    "capacity"
                ),
                "food": market.get(
                    "food"
                ),
                "max_food": market.get(
                    "max_food"
                ),
                "price": market.get(
                    "price"
                ),
            },

            "shortages": shortages,
            "surpluses": surpluses,

            "interpretation_limits": [
                (
                    "Visible foreign market prices do not by themselves "
                    "prove that a trade route is reachable or profitable."
                ),
                (
                    "Trade route distance, merchant capacity, route cost, "
                    "trade connectivity, and detailed trade-flow data are "
                    "not yet included in this briefing."
                ),
                (
                    "Import/export booleans are preserved from the save "
                    "but their exact gameplay semantics have not yet been "
                    "fully validated."
                ),
                (
                    "Only deliberately exposed player-facing fields are "
                    "included. Internal raw country AI-memory fields are "
                    "not provided to the advisor."
                ),
            ],
        }

        return self._round(
            result
        )

    # ========================================================
    # Good brief
    # ========================================================

    def good_brief(
        self,
        good: str,
        limit: int = 12,
    ):
        campaign = (
            self.world.get_campaign_state()
        )

        player = self._player_summary()

        rows = self.world.get_good_worldwide(
            good
        )

        if not rows:
            raise ValueError(
                f"No visible market data found for good: {good}"
            )

        good_key = rows[0].get(
            "good"
        )

        good_name = rows[0].get(
            "good_name"
        )

        player_market_ids = {
            row["market_id"]
            for row
            in self.world.get_country_markets(
                player["country_id"]
            )
        }

        visible_prices = []

        player_prices = []

        for row in rows:

            item = {
                "market_id": row.get(
                    "market_id"
                ),
                "market_name": row.get(
                    "market_name"
                ),
                "price": row.get(
                    "price"
                ),
                "supply": row.get(
                    "supply"
                ),
                "demand": row.get(
                    "demand"
                ),
                "surplus": row.get(
                    "surplus"
                ),
                "stockpile": row.get(
                    "stockpile"
                ),
                "raw_trade_flags": {
                    "import": row.get(
                        "is_import"
                    ),
                    "export": row.get(
                        "is_export"
                    ),
                },
            }

            if (
                row.get("market_id")
                in player_market_ids
            ):
                player_prices.append(
                    item
                )

            if len(visible_prices) < limit:
                visible_prices.append(
                    item
                )

        highest = list(
            reversed(rows[-limit:])
        )

        highest_prices = []

        for row in highest:
            highest_prices.append({
                "market_id": row.get(
                    "market_id"
                ),
                "market_name": row.get(
                    "market_name"
                ),
                "price": row.get(
                    "price"
                ),
                "supply": row.get(
                    "supply"
                ),
                "demand": row.get(
                    "demand"
                ),
                "surplus": row.get(
                    "surplus"
                ),
            })

        result = {
            "context_type": "eu5_good_brief",

            "as_of": {
                "game_date": (
                    campaign.get(
                        "game_date"
                    )
                    if campaign
                    else None
                ),
                "exact_snapshot": True,
            },

            "player": player,

            "good": {
                "key": good_key,
                "name": good_name,
            },

            "player_markets": (
                player_prices
            ),

            "lowest_visible_prices": (
                visible_prices
            ),

            "highest_visible_prices": (
                highest_prices
            ),

            "visible_markets_with_price": (
                len(rows)
            ),

            "interpretation_limits": [
                (
                    "Market price comparison does not prove route "
                    "reachability or trade profitability."
                ),
                (
                    "Trade cost, merchant capacity, connectivity, and "
                    "route-level flows are not yet represented here."
                ),
            ],
        }

        return self._round(
            result
        )
