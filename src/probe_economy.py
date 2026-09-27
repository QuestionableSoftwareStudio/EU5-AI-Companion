from pathlib import Path
from pprint import pprint
import sys
import ijson

path = Path(sys.argv[1])
PLAYER_ID = "2147"

# ------------------------------------------------------------
# Load player country
# ------------------------------------------------------------

with path.open("rb") as f:
    player = next(ijson.items(f, f"countries.database.{PLAYER_ID}"))

print("\n" + "=" * 80)
print("BOHEMIA: CURRENCY DATA")
print("=" * 80)
pprint(player.get("currency_data"))

print("\n" + "=" * 80)
print("BOHEMIA: BALANCE HISTORY")
print("=" * 80)
pprint(player.get("balance_history_2"))

print("\n" + "=" * 80)
print("BOHEMIA: ECONOMY")
print("=" * 80)
pprint(player.get("economy"))

print("\n" + "=" * 80)
print("BOHEMIA: AUTOMATED TRADE CAPACITY")
print("=" * 80)
pprint(player.get("automated_trade_capacity"))

print("\n" + "=" * 80)
print("BOHEMIA: LAST MONTH PRODUCTION")
print("=" * 80)
pprint(player.get("last_month_produced"))

print("\n" + "=" * 80)
print("BOHEMIA: OWNED LOCATION IDS")
print("=" * 80)
print(player.get("owned_locations"))

# ------------------------------------------------------------
# Discover the structure directly beneath `locations`
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("LOCATIONS: IMMEDIATE STRUCTURE")
print("=" * 80)

keys = []
root_type = None

with path.open("rb") as f:
    for prefix, event, value in ijson.parse(f):
        if prefix == "locations" and event in ("start_map", "start_array"):
            root_type = event

        if prefix == "locations" and event == "map_key":
            keys.append(value)
            if len(keys) >= 30:
                break

print("root type:", root_type)
print("first immediate keys:")
for key in keys:
    print(" ", key)

# ------------------------------------------------------------
# Grab first few markets in full so we can see the object shape
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("FIRST THREE MARKET OBJECTS")
print("=" * 80)

with path.open("rb") as f:
    for i, (market_id, market) in enumerate(
        ijson.kvitems(f, "market_manager.database")
    ):
        print(f"\nMARKET {market_id}")
        print("-" * 60)

        for key, value in market.items():
            if isinstance(value, dict):
                print(f"{key}: <dict {len(value)} keys>")
                pprint(value)
            elif isinstance(value, list):
                if len(value) <= 30:
                    print(f"{key}: {value}")
                else:
                    print(f"{key}: <list {len(value)} items>")
            else:
                print(f"{key}: {value!r}")

        if i >= 2:
            break
