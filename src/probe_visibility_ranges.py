from pathlib import Path
import re
import sys

import ijson

from visibility import VisibleLocations


path = Path(sys.argv[1])


def first(prefix):
    with path.open("rb") as f:
        try:
            return next(ijson.items(f, prefix))
        except StopIteration:
            return None


metadata = first("metadata") or {}

flag = metadata.get("flag", "")

match = re.match(
    r"^\s*([A-Za-z0-9_]+)\s*=\s*\{",
    flag
)

if not match:
    raise SystemExit("Could not resolve player tag.")

tag = match.group(1)

country_id = None

with path.open("rb") as f:
    for cid, candidate_tag in ijson.kvitems(
        f,
        "countries.tags"
    ):
        if candidate_tag == tag:
            country_id = str(cid)
            break

if country_id is None:
    raise SystemExit("Could not resolve player ID.")

encoded = first(
    f"terra_incognita.countries.{country_id}"
)

if encoded is None:
    raise SystemExit(
        "Player terra-incognita entry not found."
    )

visibility = VisibleLocations(encoded)

player = first(
    f"countries.database.{country_id}"
)

owned = {
    int(x)
    for x in player.get("owned_locations", [])
}

owned_visible = {
    x for x in owned
    if x in visibility
}


print("=" * 60)
print("EU5 VISIBILITY")
print("=" * 60)

print(f"Player:             {tag} ({country_id})")
print(f"Encoded values:     {len(encoded)}")
print(f"Visible ranges:     {len(visibility.ranges)}")
print(f"Visible locations:  {visibility.count()}")

print()
print("Ranges:")

for r in visibility.describe():
    print(
        f"  {r['start']:5d} - "
        f"{r['end']:5d}  "
        f"({r['count']:5d})"
    )

print()
print(
    f"Owned visible:      "
    f"{len(owned_visible)}/{len(owned)}"
)

missing = owned - owned_visible

if missing:
    print(
        "WARNING — owned locations outside "
        "visibility:"
    )

    print(
        sorted(missing)
    )
else:
    print(
        "All owned locations are inside "
        "the visibility map."
    )
