from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import sys


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: probe_definition_location_order.py EU5_ROOT CAMPAIGN_DB"
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

definitions_path = (
    root
    / "game"
    / "in_game"
    / "map_data"
    / "definitions.txt"
)

markets_path = (
    root
    / "game"
    / "main_menu"
    / "setup"
    / "start"
    / "03_markets.txt"
)


for path in (
    templates_path,
    definitions_path,
    markets_path,
    db_path,
):
    if not path.exists():
        raise SystemExit(
            f"Not found: {path}"
        )


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
# Load all valid location keys from location_templates.txt
# ============================================================

template_pattern = re.compile(
    r"^\s*([A-Za-z0-9_\-\.]+)\s*=\s*\{"
)

location_keys = []
location_key_set = set()


with templates_path.open(
    "r",
    encoding="utf-8-sig",
    errors="ignore",
) as f:

    for raw_line in f:

        line = strip_comment(raw_line)

        match = template_pattern.match(line)

        if not match:
            continue

        key = match.group(1)

        if key in location_key_set:
            continue

        location_keys.append(key)
        location_key_set.add(key)


# ============================================================
# Scan definitions.txt in textual order.
#
# We only retain tokens which are known location keys.
# First occurrence wins.
# ============================================================

token_pattern = re.compile(
    r"[A-Za-z0-9_\-\.]+"
)

definition_order = []
seen = set()


with definitions_path.open(
    "r",
    encoding="utf-8-sig",
    errors="ignore",
) as f:

    for raw_line in f:

        line = strip_comment(raw_line)

        for token in token_pattern.findall(line):

            if token not in location_key_set:
                continue

            if token in seen:
                continue

            seen.add(token)
            definition_order.append(token)


# ============================================================
# Read declared starting markets
# ============================================================

market_pattern = re.compile(
    r"\badd_market\s*=\s*"
    r"([A-Za-z0-9_\-\.]+)"
)

declared_markets = set()


with markets_path.open(
    "r",
    encoding="utf-8-sig",
    errors="ignore",
) as f:

    for raw_line in f:

        line = strip_comment(raw_line)

        match = market_pattern.search(line)

        if match:
            declared_markets.add(
                match.group(1)
            )


# ============================================================
# Runtime market centers
# ============================================================

conn = sqlite3.connect(db_path)

runtime_centers = [
    (
        int(market_id),
        int(center_id),
    )
    for market_id, center_id
    in conn.execute("""
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
# Score nearby index conventions
#
# static_index = runtime_id + offset
# ============================================================

results = []


for offset in range(-20, 21):

    matches = 0
    valid = 0
    mapped = []

    for market_id, runtime_id in runtime_centers:

        index = runtime_id + offset

        if not (
            0 <= index < len(definition_order)
        ):
            continue

        valid += 1

        key = definition_order[index]

        ok = key in declared_markets

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

    results.append(
        {
            "offset": offset,
            "matches": matches,
            "valid": valid,
            "mapped": mapped,
        }
    )


results.sort(
    key=lambda result: (
        result["matches"],
        result["valid"],
    ),
    reverse=True,
)

best = results[0]


# ============================================================
# Prague
# ============================================================

try:
    prague_index = (
        definition_order.index(
            "prague"
        )
    )
except ValueError:
    prague_index = None


# ============================================================
# Output
# ============================================================

print("=" * 78)
print("EU5 DEFINITIONS LOCATION-ORDER PROBE")
print("=" * 78)

print(
    f"Template locations:     "
    f"{len(location_keys)}"
)

print(
    f"Locations found in definitions: "
    f"{len(definition_order)}"
)

print(
    f"Declared markets:       "
    f"{len(declared_markets)}"
)

print(
    f"Visible runtime markets:"
    f"{len(runtime_centers)}"
)


print()
print("=" * 78)
print("TOP OFFSET CANDIDATES")
print("=" * 78)


for result in results[:10]:

    print(
        f"offset {result['offset']:+4d}: "
        f"{result['matches']:2d}/"
        f"{result['valid']:2d}"
    )


print()
print("=" * 78)
print("PRAGUE")
print("=" * 78)

print(
    f"Definition-order index: "
    f"{prague_index}"
)

if prague_index is not None:

    print(
        f"One-based position:      "
        f"{prague_index + 1}"
    )

print(
    "Observed runtime ID:     1515"
)


print()
print("=" * 78)
print(
    f"BEST OFFSET: {best['offset']:+d}"
)
print("=" * 78)


for (
    market_id,
    runtime_id,
    index,
    key,
    ok,
) in best["mapped"]:

    marker = (
        "OK"
        if ok
        else "??"
    )

    print(
        f"market {market_id:4d} | "
        f"runtime {runtime_id:5d} | "
        f"index {index:5d} | "
        f"{key:30s} | "
        f"{marker}"
    )


print()
print("=" * 78)
print("BOHEMIAN IDS USING BEST OFFSET")
print("=" * 78)


for runtime_id in range(
    1483,
    1523,
):

    index = (
        runtime_id
        + best["offset"]
    )

    if (
        0 <= index
        < len(definition_order)
    ):

        print(
            f"{runtime_id:5d} -> "
            f"{definition_order[index]}"
        )

    else:

        print(
            f"{runtime_id:5d} -> "
            "OUT OF RANGE"
        )
