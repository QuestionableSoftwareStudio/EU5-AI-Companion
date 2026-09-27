from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CampaignState:
    def __init__(self, path: str | Path):
        self.path = Path(path)

        with self.path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

    @property
    def campaign(self) -> dict[str, Any]:
        return self.data["campaign"]

    @property
    def player(self) -> dict[str, Any]:
        return self.data["player_country"]

    @property
    def locations(self) -> dict[str, dict[str, Any]]:
        return self.data["owned_locations"]

    @property
    def markets(self) -> dict[str, dict[str, Any]]:
        return self.data["markets"]

    def get_player_country(self) -> dict[str, Any]:
        return self.player

    def get_player_economy(self) -> dict[str, Any]:
        return {
            "date": self.campaign["date"],
            "tag": self.campaign["player_tag"],
            "gold": self.player.get("currency_data", {}).get("gold"),
            "balance": self.player.get("balance_history_2", {}).get("Gold"),
            "economy": self.player.get("economy", {}),
            "last_month_produced": self.player.get(
                "last_month_produced",
                {}
            ),
        }

    def get_owned_locations(self) -> dict[str, dict[str, Any]]:
        return self.locations

    def get_location(self, location_id: int | str) -> dict[str, Any] | None:
        return self.locations.get(str(location_id))

    def get_player_markets(self) -> dict[str, dict[str, Any]]:
        return self.markets

    def get_market(self, market_id: int | str) -> dict[str, Any] | None:
        return self.markets.get(str(market_id))

    def get_market_good(
        self,
        market_id: int | str,
        good: str
    ) -> dict[str, Any] | None:
        market = self.get_market(market_id)

        if market is None:
            return None

        return market.get("goods", {}).get(good)

    def get_good_summary(
        self,
        market_id: int | str,
        good: str
    ) -> dict[str, Any] | None:
        data = self.get_market_good(market_id, good)

        if data is None:
            return None

        return {
            "good": good,
            "price": data.get("price"),
            "supply": data.get("supply"),
            "demand": data.get("demand"),
            "surplus": data.get("surplus"),
            "stockpile": data.get("stockpile"),
            "import": data.get("import", False),
            "export": data.get("export", False),
            "supplied": data.get("supplied", {}),
            "demanded": data.get("demanded", {}),
            "production_supplied": data.get(
                "production_supplied",
                {}
            ),
            "history": data.get("history", []),
            "priority": data.get("priority"),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "date": self.campaign["date"],
            "country": self.campaign["player_tag"],
            "country_id": self.campaign["player_country_id"],
            "gold": self.player.get(
                "currency_data",
                {}
            ).get("gold"),
            "income": self.player.get(
                "economy",
                {}
            ).get("income"),
            "expense": self.player.get(
                "economy",
                {}
            ).get("expense"),
            "owned_locations": len(self.locations),
            "markets": list(self.markets.keys()),
            "population": self.player.get(
                "last_months_population"
            ),
            "great_power": self.player.get("great_power"),
            "great_power_rank": self.player.get(
                "great_power_rank"
            ),
            "technology_level": self.player.get(
                "starting_technology_level"
            ),
        }
