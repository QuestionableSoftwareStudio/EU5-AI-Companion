from pathlib import Path
from pprint import pprint
import sys
import ijson

path = Path(sys.argv[1])

PLAYER_ID = "2147"
CANDIDATE_MARKET = "23"

# ------------------------------------------------------------
# Player
# ------------------------------------------------------------

with path.open("rb") as f:
    player = next(ijson.items(f, f"countries.database.{PLAYER_ID}"))

owned = {str(x) for x in player["owned_locations"]}
capital = str(player["capital"])

print("=" * 80)
print("PLAYER")
print("=" * 80)
print("country:", player["country_name"])
print("capital location:", capital)
print("owned locations:", len(owned))
print("automated trade capacity:", player.get("automated_trade_capacity"))

# ------------------------------------------------------------
# Inspect structure of locations.locations
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("LOCATIONS.LOCATIONS STRUCTURE")
print("=" * 80)

seen = 0

with path.open("rb") as f:
    for prefix, event, value in ijson.parse(f):

        if prefix == "locations.locations":
            if event in ("start_map", "start_array"):
                print("root:", event)

            elif event == "map_key":
                print("first location key:", value)
                break

# ------------------------------------------------------------
# Pull only Bohemia's owned location objects
# ------------------------------------------------------------

bohemian_locations = {}

with path.open("rb") as f:
    for loc_id, loc in ijson.kvitems(f, "locations.locations"):
        if str(loc_id) in owned:
            bohemian_locations[str(loc_id)] = loc

print("\nLoaded owned location objects:", len(bohemian_locations))

KEYWORDS = (
    "name",
    "owner",
    "controller",
    "market",
    "province",
    "population",
    "raw",
    "good",
    "rgo",
    "food",
    "tax",
    "development",
    "prosperity",
)

def interesting(obj):
    result = {}

    for key, value in obj.items():
        lower = str(key).lower()

        if any(word in lower for word in KEYWORDS):
            result[key] = value

    return result

# ------------------------------------------------------------
# Capital
# ------------------------------------------------------------

print("\n" + "=" * 80)
print(f"CAPITAL LOCATION {capital}")
print("=" * 80)

cap = bohemian_locations.get(capital)

if cap is None:
    print("Capital object not found!")
else:
    pprint(interesting(cap))

    print("\nCapital top-level keys:")
    print(", ".join(cap.keys()))

# ------------------------------------------------------------
# First 10 owned locations
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("FIRST 10 BOHEMIAN LOCATIONS")
print("=" * 80)

for loc_id in list(map(str, player["owned_locations"]))[:10]:
    loc = bohemian_locations.get(loc_id)

    print(f"\nLOCATION {loc_id}")

    if loc is None:
        print("  NOT FOUND")
        continue

    pprint(interesting(loc))

# ------------------------------------------------------------
# Candidate market 23
# ------------------------------------------------------------

print("\n" + "=" * 80)
print(f"MARKET {CANDIDATE_MARKET}")
print("=" * 80)

with path.open("rb") as f:
    try:
        market = next(
            ijson.items(
                f,
                f"market_manager.database.{CANDIDATE_MARKET}"
            )
        )
    except StopIteration:
        market = None

if market is None:
    print("Market not found.")
else:
    for key in (
        "center",
        "food",
        "max",
        "price",
        "population",
        "capacity",
        "market",
        "language",
        "dialect",
        "merchant",
    ):
        if key in market:
            print(f"{key}:")
            pprint(market[key])

    goods = market.get("goods", {})

    print("\nSelected goods:")
    for good in (
        "iron",
        "copper",
        "tools",
        "weaponry",
        "lumber",
        "stone",
        "silver",
        "paper",
        "books",
    ):
        if good in goods:
            print(f"\n{good.upper()}")
            pprint(goods[good])
