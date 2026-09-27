from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json
import re
import sys

import ijson


source = Path(sys.argv[1])
output = Path(sys.argv[2])


def decimal_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value)}")


def first(prefix):
    with source.open("rb") as f:
        try:
            return next(ijson.items(f, prefix))
        except StopIteration:
            return None


# ============================================================
# Very cheap early-save reads
# ============================================================

metadata = first("metadata") or {}
date = first("start_of_day")

if date is None:
    raise SystemExit("Could not find start_of_day")


# ============================================================
# Resolve player tag
#
# EU5 metadata.flag looks like:
#
#   BOH={
#       pattern="..."
#       ...
#   }
#
# So extract BOH from the beginning rather than treating the
# complete coat-of-arms definition as the tag.
# ============================================================

flag = metadata.get("flag", "")

player_tag = None

if isinstance(flag, str):
    match = re.match(
        r"^\s*([A-Za-z0-9_]+)\s*=\s*\{",
        flag
    )

    if match:
        player_tag = match.group(1)


# ============================================================
# Fast path: tag known from metadata.flag
# ============================================================

player_id = None

if player_tag:
    with source.open("rb") as f:
        for db_id, tag in ijson.kvitems(
            f,
            "countries.tags"
        ):
            if tag == player_tag:
                player_id = str(db_id)
                break


# ============================================================
# Safety fallback
#
# Only do the expensive late-save played_country lookup if
# metadata.flag ever changes format in a future EU5 version.
# ============================================================

if player_id is None:
    played_country = first("played_country")

    if (
        not played_country
        or "country" not in played_country
    ):
        raise SystemExit(
            "Could not determine played country."
        )

    player_id = str(played_country["country"])

    with source.open("rb") as f:
        for db_id, tag in ijson.kvitems(
            f,
            "countries.tags"
        ):
            if str(db_id) == player_id:
                player_tag = tag
                break


if player_id is None:
    raise SystemExit("Could not resolve player country ID")

if player_tag is None:
    raise SystemExit("Could not resolve player country tag")


# ============================================================
# Complete player country
#
# ijson.items() lets the YAJL C backend skip everything that
# isn't the requested object without constructing it.
# ============================================================

player = first(
    f"countries.database.{player_id}"
)

if player is None:
    raise SystemExit(
        f"Country object {player_id} not found."
    )


# Verify our metadata.flag shortcut against the actual country.
country_tag_check = player.get("country_name")

if (
    country_tag_check is not None
    and country_tag_check != player_tag
):
    raise SystemExit(
        "Player tag verification failed: "
        f"metadata={player_tag!r}, "
        f"country={country_tag_check!r}"
    )


owned_ids = {
    str(x)
    for x in player.get("owned_locations", [])
}

if not owned_ids:
    raise SystemExit(
        "Player country has no owned locations."
    )


# ============================================================
# Owned locations
#
# Important optimization:
#
# STOP as soon as all owned location IDs have been collected.
# We do not need to parse the rest of the world's enormous
# location objects for this player-slice extractor.
# ============================================================

owned_locations = {}

with source.open("rb") as f:
    for loc_id, loc in ijson.kvitems(
        f,
        "locations.locations"
    ):
        loc_id = str(loc_id)

        if loc_id in owned_ids:
            owned_locations[loc_id] = loc

            if len(owned_locations) == len(owned_ids):
                break


missing_locations = (
    owned_ids - set(owned_locations)
)

if missing_locations:
    raise SystemExit(
        "Missing owned locations: "
        + ", ".join(
            sorted(missing_locations, key=int)
        )
    )


# ============================================================
# Markets used by those locations
# ============================================================

market_ids = {
    str(loc["market"])
    for loc in owned_locations.values()
    if loc.get("market") is not None
}


# ============================================================
# Complete market objects
#
# For a small number of player markets, direct-prefix lookup is
# faster than constructing every earlier market via kvitems().
#
# If a future country spans many markets we can switch strategy.
# ============================================================

markets = {}

if len(market_ids) <= 4:
    for market_id in sorted(
        market_ids,
        key=int
    ):
        market = first(
            f"market_manager.database.{market_id}"
        )

        if market is not None:
            markets[market_id] = market

else:
    with source.open("rb") as f:
        for market_id, market in ijson.kvitems(
            f,
            "market_manager.database"
        ):
            market_id = str(market_id)

            if market_id in market_ids:
                markets[market_id] = market

                if len(markets) == len(market_ids):
                    break


missing_markets = (
    market_ids - set(markets)
)

if missing_markets:
    raise SystemExit(
        "Missing markets: "
        + ", ".join(
            sorted(missing_markets, key=int)
        )
    )


# ============================================================
# Snapshot
# ============================================================

snapshot = {
    "campaign": {
        "date": date,
        "version": metadata.get("version"),
        "playthrough_id": metadata.get(
            "playthrough_id"
        ),
        "player_country_id": int(player_id),
        "player_tag": player_tag,
        "player_country_name": metadata.get(
            "player_country_name"
        ),
    },

    "player_country": player,
    "owned_locations": owned_locations,
    "markets": markets,
}


output.parent.mkdir(
    parents=True,
    exist_ok=True,
)

with output.open(
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        snapshot,
        f,
        ensure_ascii=False,
        separators=(",", ":"),
        default=decimal_default,
    )


print("EU5 PLAYER SNAPSHOT")
print("=" * 60)
print(f"Date:              {date}")
print(f"Country:           {player_tag}")
print(f"Country DB id:     {player_id}")
print(f"Owned locations:   {len(owned_locations)}")
print(
    "Market IDs:        "
    f"{sorted(market_ids, key=int)}"
)
print(f"Markets extracted: {len(markets)}")
print(
    "Output size:       "
    f"{output.stat().st_size / 1024 / 1024:.2f} MB"
)
print(f"Output:            {output}")
