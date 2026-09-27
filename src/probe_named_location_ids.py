from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import sys


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: probe_named_location_ids.py EU5_ROOT CAMPAIGN_DB"
    )

root = Path(sys.argv[1]).resolve()
db_path = Path(sys.argv[2]).resolve()

named_path = (
    root
    / "game"
    / "in_game"
    / "map_data"
    / "named_locations"
    / "00_default.txt"
)

markets_path = (
    root
    / "game"
    / "main_menu"
    / "setup"
    / "start"
    / "03_markets.txt"
)

if not named_path.exists():
    raise SystemExit(f"Not found: {named_path}")

if not markets_path.exists():
    raise SystemExit(f"Not found: {markets_path}")

if not db_path.exists():
    raise SystemExit(f"Not found: {db_path}")


def strip_comment(line: str):
    result = []
    in_string = False
    escaped = False

    for char in line:
        if escaped:
            result.append(char)
            escaped = False
            continue

        if char == "\\":
            result.append(char)
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            result.append(char)
            continue

        if char == "#" and not in_string:
            break

        result.append(char)

    return "".join(result)


# ============================================================
# Parse named_locations in FILE ORDER
#
# Format:
#
# stockholm = abcdef
# ...
# prague = bb583d
# ============================================================

named_pattern = re.compile(
    r"^\s*([A-Za-z0-9_\-\.]+)\s*=\s*"
    r"([0-9A-Fa-f]{6})\s*$"
)

named_entries = []

with named_path.open(
    "r",
    encoding="utf-8-sig",
    errors="ignore",
) as f:

    for line_number, raw_line in enumerate(f, start=1):

        line = strip_comment(raw_line).strip()

        match = named_pattern.match(line)

        if not match:
            continue

        named_entries.append({
            "key": match.group(1),
            "color": match.group(2).lower(),
            "line": line_number,
        })


# ============================================================
# Starting market-center keys
# ============================================================

market_pattern = re.compile(
    r"\badd_market\s*=\s*([A-Za-z0-9_\-\.]+)"
)

static_market_centers = set()

with markets_path.open(
    "r",
    encoding="utf-8-sig",
    errors="ignore",
) as f:

    for raw_line in f:

        line = strip_comment(raw_line)

        match = market_pattern.search(line)

        if match:
            static_market_centers.add(
                match.group(1)
            )


# ============================================================
# Runtime market centers
# ============================================================

conn = sqlite3.connect(db_path)

runtime_centers = [
    (int(mid), int(center))
    for mid, center in conn.execute("""
        SELECT
            market_id,
            center_location_id
        FROM current_markets
        WHERE center_location_id IS NOT NULL
        ORDER BY market_id
    """)
]

conn.close()


# ============================================================
# Test zero-based and one-based mappings
# ============================================================

def score(index_offset):
    """
    static index = runtime ID + index_offset

    one-based runtime IDs:
        runtime 1 -> index 0
        offset = -1

    zero-based runtime IDs:
        runtime 0 -> index 0
        offset = 0
    """

    mapped = []
    matches = 0

    for market_id, runtime_id in runtime_centers:

        index = runtime_id + index_offset

        if not (0 <= index < len(named_entries)):
            mapped.append(
                (
                    market_id,
                    runtime_id,
                    index,
                    None,
                    False,
                )
            )
            continue

        key = named_entries[index]["key"]

        ok = key in static_market_centers

        if ok:
            matches += 1

        mapped.append(
            (
                market_id,
                runtime_id,
                index,
                key,
                ok,
            )
        )

    return matches, mapped


zero_matches, zero_mapped = score(0)
one_matches, one_mapped = score(-1)


print("=" * 76)
print("EU5 NAMED-LOCATION ID PROBE")
print("=" * 76)

print(f"Named locations:        {len(named_entries)}")
print(f"Static market centers:  {len(static_market_centers)}")
print(f"Runtime visible markets:{len(runtime_centers)}")

print()
print("ID hypotheses:")
print(
    f"  runtime ID == zero-based index: "
    f"{zero_matches}/{len(runtime_centers)}"
)
print(
    f"  runtime ID == one-based index:  "
    f"{one_matches}/{len(runtime_centers)}"
)


# ============================================================
# Prague
# ============================================================

prague_index = None

for index, entry in enumerate(named_entries):
    if entry["key"] == "prague":
        prague_index = index
        break


print()
print("=" * 76)
print("PRAGUE")
print("=" * 76)

print(f"Named-location zero index: {prague_index}")

if prague_index is not None:
    print(
        f"Named-location one ID:     "
        f"{prague_index + 1}"
    )

print("Observed runtime ID:       1515")


# ============================================================
# Best hypothesis details
# ============================================================

if one_matches >= zero_matches:
    best_name = "ONE-BASED"
    best = one_mapped
else:
    best_name = "ZERO-BASED"
    best = zero_mapped


print()
print("=" * 76)
print(f"BEST: {best_name}")
print("=" * 76)


for (
    market_id,
    runtime_id,
    index,
    key,
    ok,
) in best:

    marker = "OK" if ok else "??"

    print(
        f"market {market_id:4d} | "
        f"runtime {runtime_id:5d} | "
        f"index {index:5d} | "
        f"{str(key):30s} | "
        f"{marker}"
    )


# ============================================================
# Direct Bohemian runtime range
# ============================================================

print()
print("=" * 76)
print("BOHEMIAN IDS")
print("=" * 76)

bohemian_ids = range(1483, 1523)

offset = -1 if best_name == "ONE-BASED" else 0

for runtime_id in bohemian_ids:

    index = runtime_id + offset

    if 0 <= index < len(named_entries):
        print(
            f"{runtime_id:5d} -> "
            f"{named_entries[index]['key']}"
        )
    else:
        print(
            f"{runtime_id:5d} -> OUT OF RANGE"
        )
