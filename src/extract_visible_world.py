from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json
import re
import sys
import time

import ijson

from visibility import VisibleLocations


source = Path(sys.argv[1])
output = Path(sys.argv[2])


def decimal_default(value):
    if isinstance(value, Decimal):
        return float(value)

    raise TypeError(
        f"Cannot serialize {type(value)}"
    )


def first(prefix):
    with source.open("rb") as f:
        try:
            return next(
                ijson.items(f, prefix)
            )
        except StopIteration:
            return None


started_total = time.perf_counter()


# ============================================================
# Campaign + player identity
# ============================================================

metadata = first("metadata") or {}
date = first("start_of_day")

if date is None:
    raise SystemExit(
        "Could not find start_of_day"
    )


flag = metadata.get("flag", "")

match = None

if isinstance(flag, str):
    match = re.match(
        r"^\s*([A-Za-z0-9_]+)\s*=\s*\{",
        flag
    )

if not match:
    raise SystemExit(
        "Could not resolve player tag "
        "from metadata.flag"
    )

player_tag = match.group(1)


# ============================================================
# Country tags
#
# This mapping is cheap and useful later too.
# ============================================================

country_tags = {}

with source.open("rb") as f:
    for country_id, tag in ijson.kvitems(
        f,
        "countries.tags"
    ):
        country_tags[str(country_id)] = tag


player_id = None

for country_id, tag in country_tags.items():
    if tag == player_tag:
        player_id = country_id
        break

if player_id is None:
    raise SystemExit(
        f"Could not resolve ID for {player_tag}"
    )


# ============================================================
# Visibility
# ============================================================

encoded_visibility = first(
    f"terra_incognita.countries.{player_id}"
)

if encoded_visibility is None:
    raise SystemExit(
        "Player visibility entry not found."
    )

visibility = VisibleLocations(
    encoded_visibility
)

print("EU5 VISIBLE WORLD EXTRACTOR")
print("=" * 60)
print(
    f"Player:            "
    f"{player_tag} ({player_id})"
)
print(f"Game date:         {date}")
print(
    f"Visible locations: "
    f"{visibility.count()}"
)


# ============================================================
# Visible locations
#
# Collect complete location objects for every location the
# player is allowed to see.
#
# At the same time derive:
#   - countries with visible territorial presence
#   - markets visible through visible locations
# ============================================================

print()
print("[1/3] Extracting visible locations...")

started = time.perf_counter()

visible_locations = {}

visible_country_ids = {
    player_id
}

visible_market_ids = set()


with source.open("rb") as f:
    for location_id, location in ijson.kvitems(
        f,
        "locations.locations"
    ):
        location_id_str = str(location_id)

        if int(location_id) not in visibility:
            continue

        visible_locations[
            location_id_str
        ] = location

        owner = location.get("owner")

        if owner is not None and int(owner) > 0:
            visible_country_ids.add(
                str(owner)
            )

        controller = location.get(
            "controller"
        )

        if (
            controller is not None
            and int(controller) > 0
        ):
            visible_country_ids.add(
                str(controller)
            )

        market = location.get("market")

        if market is not None:
            visible_market_ids.add(
                str(market)
            )


location_seconds = (
    time.perf_counter() - started
)

print(
    f"      {len(visible_locations)} locations "
    f"in {location_seconds:.2f}s"
)

print(
    f"      {len(visible_country_ids)} "
    f"territorial countries"
)

print(
    f"      {len(visible_market_ids)} "
    f"markets referenced"
)


# ============================================================
# Visible territorial countries
# ============================================================

print()
print("[2/3] Extracting visible countries...")

started = time.perf_counter()

visible_countries = {}


with source.open("rb") as f:
    for country_id, country in ijson.kvitems(
        f,
        "countries.database"
    ):
        country_id = str(country_id)

        if country_id not in visible_country_ids:
            continue

        visible_countries[
            country_id
        ] = country

        if (
            len(visible_countries)
            == len(visible_country_ids)
        ):
            break


country_seconds = (
    time.perf_counter() - started
)

missing_countries = (
    visible_country_ids
    - set(visible_countries)
)

if missing_countries:
    print(
        "      WARNING: missing country objects:",
        sorted(
            missing_countries,
            key=int
        )
    )

print(
    f"      {len(visible_countries)} countries "
    f"in {country_seconds:.2f}s"
)


# ============================================================
# Markets used by visible locations
# ============================================================

print()
print("[3/3] Extracting visible markets...")

started = time.perf_counter()

visible_markets = {}


with source.open("rb") as f:
    for market_id, market in ijson.kvitems(
        f,
        "market_manager.database"
    ):
        market_id = str(market_id)

        if market_id not in visible_market_ids:
            continue

        visible_markets[
            market_id
        ] = market

        if (
            len(visible_markets)
            == len(visible_market_ids)
        ):
            break


market_seconds = (
    time.perf_counter() - started
)

missing_markets = (
    visible_market_ids
    - set(visible_markets)
)

if missing_markets:
    print(
        "      WARNING: missing market objects:",
        sorted(
            missing_markets,
            key=int
        )
    )

print(
    f"      {len(visible_markets)} markets "
    f"in {market_seconds:.2f}s"
)


# ============================================================
# Build snapshot
# ============================================================

country_tag_subset = {
    country_id: country_tags.get(
        country_id
    )
    for country_id
    in visible_country_ids
}


snapshot = {
    "campaign": {
        "date": date,
        "version": metadata.get(
            "version"
        ),
        "playthrough_id": metadata.get(
            "playthrough_id"
        ),
        "player_country_id": int(
            player_id
        ),
        "player_tag": player_tag,
        "player_country_name": (
            metadata.get(
                "player_country_name"
            )
        ),
        "visibility": {
            "encoding": (
                "terra_incognita_rle"
            ),
            "location_count": (
                visibility.count()
            ),
            "ranges": (
                visibility.describe()
            ),
        },
    },

    "country_tags": (
        country_tag_subset
    ),

    "countries": (
        visible_countries
    ),

    "locations": (
        visible_locations
    ),

    "markets": (
        visible_markets
    ),
}


output.parent.mkdir(
    parents=True,
    exist_ok=True
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


total_seconds = (
    time.perf_counter() - started_total
)


print()
print("=" * 60)
print("VISIBLE WORLD READY")
print("=" * 60)

print(
    f"Locations:   "
    f"{len(visible_locations)}"
)

print(
    f"Countries:   "
    f"{len(visible_countries)}"
)

print(
    f"Markets:     "
    f"{len(visible_markets)}"
)

print(
    f"Output size: "
    f"{output.stat().st_size / 1024 / 1024:.2f} MB"
)

print(
    f"Total time:  "
    f"{total_seconds:.2f}s"
)

print(
    f"Output:      {output}"
)
