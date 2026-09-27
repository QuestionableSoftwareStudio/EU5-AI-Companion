from __future__ import annotations

from pathlib import Path
from pprint import pprint
import re
import sys

import ijson


path = Path(sys.argv[1])


def first(prefix):
    with path.open("rb") as f:
        try:
            return next(ijson.items(f, prefix))
        except StopIteration:
            return None


def summarize(name, value, limit=20):
    print()
    print("-" * 70)
    print(name)
    print("-" * 70)

    if value is None:
        print("NOT FOUND")
        return

    print("type:", type(value).__name__)

    if isinstance(value, dict):
        print("keys:", list(value.keys()))

        for key, child in value.items():
            if isinstance(child, dict):
                print(f"{key}: dict({len(child)})")

                sample = list(child.items())[:limit]
                if sample:
                    print("  sample:")
                    for k, v in sample:
                        if isinstance(v, (dict, list)):
                            print(
                                f"    {k!r}: "
                                f"{type(v).__name__}({len(v)})"
                            )
                        else:
                            print(f"    {k!r}: {v!r}")

            elif isinstance(child, list):
                print(
                    f"{key}: list({len(child)}) "
                    f"sample={child[:limit]!r}"
                )

            else:
                print(f"{key}: {child!r}")

    elif isinstance(value, list):
        print("length:", len(value))
        print("sample:")
        pprint(value[:limit])

    else:
        pprint(value)


# ============================================================
# Resolve player
# ============================================================

metadata = first("metadata") or {}

flag = metadata.get("flag", "")

player_tag = None

if isinstance(flag, str):
    match = re.match(
        r"^\s*([A-Za-z0-9_]+)\s*=\s*\{",
        flag
    )

    if match:
        player_tag = match.group(1)

if not player_tag:
    raise SystemExit(
        "Could not resolve player tag from metadata.flag"
    )


player_id = None

with path.open("rb") as f:
    for country_id, tag in ijson.kvitems(
        f,
        "countries.tags"
    ):
        if tag == player_tag:
            player_id = str(country_id)
            break

if player_id is None:
    raise SystemExit(
        f"Could not resolve ID for {player_tag}"
    )


print("=" * 70)
print("EU5 VISIBILITY PROBE")
print("=" * 70)
print("Player tag:", player_tag)
print("Player ID: ", player_id)


# ============================================================
# Player's terra-incognita entry
# ============================================================

player_ti = first(
    f"terra_incognita.countries.{player_id}"
)

summarize(
    f"TERRA INCOGNITA — PLAYER {player_id}",
    player_ti
)


# ============================================================
# First few entries under terra_incognita.countries
#
# This tells us whether the map is keyed by viewing country,
# target country, or something else.
# ============================================================

print()
print("=" * 70)
print("FIRST 8 TERRA_INCOGNITA COUNTRY ENTRIES")
print("=" * 70)

with path.open("rb") as f:
    count = 0

    for country_id, obj in ijson.kvitems(
        f,
        "terra_incognita.countries"
    ):
        print()
        print(f"COUNTRY KEY {country_id}")
        print("type:", type(obj).__name__)

        if isinstance(obj, dict):
            print("keys:", list(obj.keys()))

            for key, value in obj.items():
                if isinstance(value, dict):
                    print(
                        f"  {key}: dict({len(value)})"
                    )
                elif isinstance(value, list):
                    print(
                        f"  {key}: list({len(value)}) "
                        f"sample={value[:10]!r}"
                    )
                else:
                    print(
                        f"  {key}: {value!r}"
                    )

        elif isinstance(obj, list):
            print(
                f"length: {len(obj)}, "
                f"sample={obj[:10]!r}"
            )

        else:
            pprint(obj)

        count += 1

        if count >= 8:
            break


# ============================================================
# Player proximity cache
#
# We saw this field on country objects earlier. It may encode
# another notion of countries/locations considered reachable
# or known, so inspect it alongside terra incognita.
# ============================================================

proximity = first(
    f"countries.database.{player_id}."
    "proximity_persistent_cache"
)

summarize(
    "PLAYER PROXIMITY_PERSISTENT_CACHE",
    proximity
)
