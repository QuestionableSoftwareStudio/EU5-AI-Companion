from pathlib import Path
import sys
import ijson

path = Path(sys.argv[1])

PLAYER_ID = "2147"

# Find the tag associated with the player DB id.
player_tag = None
with path.open("rb") as f:
    for key, value in ijson.kvitems(f, "countries.tags"):
        if str(key) == PLAYER_ID:
            player_tag = value
            break

print(f"Player DB id: {PLAYER_ID}")
print(f"Player tag:   {player_tag}")
print()

# Load just Bohemia's country object, not the entire save.
player = None
with path.open("rb") as f:
    for obj in ijson.items(f, f"countries.database.{PLAYER_ID}"):
        player = obj
        break

if player is None:
    raise SystemExit("Could not find player country object.")

print("PLAYER COUNTRY TOP-LEVEL KEYS")
print("=" * 70)

for key, value in player.items():
    if isinstance(value, dict):
        print(f"{key:<45} dict ({len(value)} keys)")
    elif isinstance(value, list):
        print(f"{key:<45} list ({len(value)} items)")
    else:
        text = repr(value)
        if len(text) > 100:
            text = text[:97] + "..."
        print(f"{key:<45} {text}")

KEYWORDS = (
    "market",
    "gold",
    "treasury",
    "income",
    "expense",
    "tax",
    "revenue",
    "budget",
    "loan",
    "debt",
    "trade",
    "production",
    "goods",
    "price",
    "population",
    "manpower",
    "army",
    "unit",
    "military",
    "advance",
    "research",
    "technology",
)

matches = []

def walk(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else str(key)

            if any(word in str(key).lower() for word in KEYWORDS):
                if isinstance(value, (dict, list)):
                    shown = f"<{type(value).__name__}: {len(value)}>"
                else:
                    shown = repr(value)
                    if len(shown) > 160:
                        shown = shown[:157] + "..."

                matches.append((new_path, shown))

            walk(value, new_path)

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            walk(value, f"{path}[{i}]")

walk(player)

print()
print("ECONOMY / MARKET / MILITARY / RESEARCH PATHS")
print("=" * 70)

for p, v in matches[:300]:
    print(f"{p}")
    print(f"    {v}")

if len(matches) > 300:
    print(f"\n... {len(matches) - 300} more matches omitted")
