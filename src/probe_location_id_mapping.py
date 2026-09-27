from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import sys


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: probe_location_id_mapping.py EU5_ROOT CAMPAIGN_DB"
    )


root = Path(sys.argv[1]).resolve()
db_path = Path(sys.argv[2]).resolve()

templates_path = (
    root
    / "game"
    / "in_game"
    / "map_data"
    / "location_templates.txt"
)

markets_path = (
    root
    / "game"
    / "main_menu"
    / "setup"
    / "start"
    / "03_markets.txt"
)


if not templates_path.exists():
    raise SystemExit(
        f"Not found: {templates_path}"
    )

if not markets_path.exists():
    raise SystemExit(
        f"Not found: {markets_path}"
    )

if not db_path.exists():
    raise SystemExit(
        f"Not found: {db_path}"
    )


# ============================================================
# Helpers
# ============================================================

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


def brace_delta(line: str):
    delta = 0

    in_string = False
    escaped = False

    for char in line:

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            delta += 1

        elif char == "}":
            delta -= 1

    return delta


# ============================================================
# Parse ordered location templates
# ============================================================

entry_pattern = re.compile(
    r"^\s*([A-Za-z0-9_\-\.]+)\s*=\s*\{"
)

entries = []

depth = 0


with templates_path.open(
    "r",
    encoding="utf-8-sig",
    errors="ignore",
) as f:

    for line_number, raw_line in enumerate(
        f,
        start=1,
    ):

        line = strip_comment(raw_line)

        if depth == 0:

            match = entry_pattern.match(line)

            if match:
                entries.append(
                    {
                        "key": match.group(1),
                        "line": line_number,
                    }
                )

        depth += brace_delta(line)


# ============================================================
# Parse all starting market-center location keys
# ============================================================

market_pattern = re.compile(
    r"\badd_market\s*=\s*"
    r"([A-Za-z0-9_\-\.]+)"
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
# Get visible runtime market centers from SQLite
# ============================================================

conn = sqlite3.connect(db_path)

rows = conn.execute("""
    SELECT
        market_id,
        center_location_id
    FROM current_markets
    ORDER BY market_id
""").fetchall()

conn.close()


runtime_centers = [
    (
        int(market_id),
        int(center_id),
    )
    for market_id, center_id in rows
    if center_id is not None
]


# ============================================================
# Score candidate offsets
#
# static_index = runtime_id + offset
#
# Prague:
#
#   runtime = 1515
#   static index = 1502
#
# therefore expected offset = -13
# ============================================================

results = []


for offset in range(-100, 101):

    matches = 0
    valid = 0

    mapped = []

    for market_id, runtime_id in runtime_centers:

        index = runtime_id + offset

        if not (
            0 <= index < len(entries)
        ):
            continue

        valid += 1

        key = entries[index]["key"]

        is_market = (
            key in static_market_centers
        )

        if is_market:
            matches += 1

        mapped.append(
            (
                market_id,
                runtime_id,
                index,
                key,
                is_market,
            )
        )

    results.append(
        {
            "offset": offset,
            "matches": matches,
            "valid": valid,
            "mapped": mapped,
        }
    )


results.sort(
    key=lambda x: (
        x["matches"],
        x["valid"],
    ),
    reverse=True,
)


# ============================================================
# Output
# ============================================================

print("=" * 76)
print("EU5 LOCATION-ID MAPPING PROBE")
print("=" * 76)

print(
    f"Location templates:     {len(entries)}"
)

print(
    f"Static market centers:  {len(static_market_centers)}"
)

print(
    f"Visible runtime markets:{len(runtime_centers)}"
)


print()
print("=" * 76)
print("TOP OFFSET CANDIDATES")
print("=" * 76)


for result in results[:15]:

    print(
        f"offset {result['offset']:+4d}: "
        f"{result['matches']:2d}/"
        f"{result['valid']:2d} "
        f"map to declared market centers"
    )


best = results[0]


print()
print("=" * 76)
print(
    f"BEST OFFSET: {best['offset']:+d}"
)
print("=" * 76)


for (
    market_id,
    runtime_id,
    index,
    key,
    is_market,
) in best["mapped"]:

    marker = (
        "OK"
        if is_market
        else "??"
    )

    print(
        f"market {market_id:4d} | "
        f"runtime {runtime_id:5d} | "
        f"static {index:5d} | "
        f"{key:30s} | "
        f"{marker}"
    )


# ============================================================
# Explicit Prague check
# ============================================================

print()
print("=" * 76)
print("PRAGUE CHECK")
print("=" * 76)


prague_index = None

for index, entry in enumerate(entries):

    if entry["key"] == "prague":
        prague_index = index
        break


print(
    f"Static Prague index:  {prague_index}"
)

print(
    f"Expected runtime ID:  "
    f"{prague_index - best['offset']}"
)

print(
    "Observed runtime ID: 1515"
)


# ============================================================
# Bohemia capital neighborhood using best mapping
# ============================================================

print()
print("=" * 76)
print("BOHEMIAN RUNTIME IDS USING BEST OFFSET")
print("=" * 76)


bohemian_ids = [
    1483, 1484, 1485, 1486, 1487,
    1488, 1489, 1490, 1491, 1492,
    1493, 1494, 1495, 1496, 1497,
    1498, 1499, 1500, 1501, 1502,
    1503, 1504, 1505, 1506, 1507,
    1508, 1509, 1510, 1511, 1512,
    1513, 1514, 1515, 1516, 1517,
    1518, 1519, 1520, 1521, 1522,
]


for runtime_id in bohemian_ids:

    index = (
        runtime_id
        + best["offset"]
    )

    if 0 <= index < len(entries):

        print(
            f"{runtime_id:5d} -> "
            f"{entries[index]['key']}"
        )

    else:

        print(
            f"{runtime_id:5d} -> "
            "OUT OF RANGE"
        )
