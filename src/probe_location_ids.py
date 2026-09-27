from __future__ import annotations

from pathlib import Path
import re
import sys


if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: probe_location_ids.py EU5_ROOT"
    )

root = Path(sys.argv[1]).resolve()

templates_path = (
    root
    / "game"
    / "in_game"
    / "map_data"
    / "location_templates.txt"
)

if not templates_path.exists():
    raise SystemExit(
        f"Not found: {templates_path}"
    )


# Known runtime IDs from our Bohemia save.
bohemian_ids = [
    1073,
    1074,
    1076,
    1077,
    1078,

    1483,
    1484,
    1485,
    1486,
    1487,
    1488,
    1489,
    1490,
    1491,
    1492,
    1493,
    1494,
    1495,
    1496,
    1497,
    1498,
    1499,
    1500,
    1501,
    1502,
    1503,
    1504,
    1505,
    1506,
    1507,
    1508,
    1509,
    1510,
    1511,
    1512,
    1513,
    1514,
    1515,
    1516,
    1517,
    1518,
    1519,
    1520,
    1521,
    1522,
]


def strip_comment(line: str):
    """
    Remove # comments while respecting quoted strings.
    """

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
    """
    Count { and } outside quoted strings.
    """

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

        # Only definitions beginning at file top level.
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


print("=" * 72)
print("EU5 LOCATION-ID ORDER PROBE")
print("=" * 72)

print("File:", templates_path)
print("Top-level locations:", len(entries))


# ------------------------------------------------------------
# Prague's position
# ------------------------------------------------------------

prague_index = None

for index, entry in enumerate(entries):

    if entry["key"] == "prague":
        prague_index = index
        break


print()
print("PRAGUE")

if prague_index is None:

    print("  NOT FOUND")

else:

    print(
        f"  zero-based index: {prague_index}"
    )

    print(
        f"  one-based index:  {prague_index + 1}"
    )

    print(
        f"  source line:      "
        f"{entries[prague_index]['line']}"
    )


# ------------------------------------------------------------
# Check likely ID offsets around Prague
# ------------------------------------------------------------

print()
print("RUNTIME ID 1515 HYPOTHESES")

for offset in range(-5, 6):

    index = 1515 + offset

    if 0 <= index < len(entries):

        print(
            f"  index {index:5d} "
            f"(id + {offset:+d})"
            f" -> {entries[index]['key']}"
        )


# ------------------------------------------------------------
# Two obvious hypotheses:
#
# runtime ID == zero-based array index
# runtime ID == one-based array index
# ------------------------------------------------------------

print()
print("=" * 72)
print("BOHEMIAN IDS — ZERO-BASED HYPOTHESIS")
print("=" * 72)

for runtime_id in bohemian_ids:

    if 0 <= runtime_id < len(entries):

        entry = entries[runtime_id]

        print(
            f"{runtime_id:5d} -> "
            f"{entry['key']}"
        )

    else:

        print(
            f"{runtime_id:5d} -> OUT OF RANGE"
        )


print()
print("=" * 72)
print("BOHEMIAN IDS — ONE-BASED HYPOTHESIS")
print("=" * 72)

for runtime_id in bohemian_ids:

    index = runtime_id - 1

    if 0 <= index < len(entries):

        entry = entries[index]

        print(
            f"{runtime_id:5d} -> "
            f"{entry['key']}"
        )

    else:

        print(
            f"{runtime_id:5d} -> OUT OF RANGE"
        )


# ------------------------------------------------------------
# Entries around Prague for visual sanity.
# ------------------------------------------------------------

if prague_index is not None:

    print()
    print("=" * 72)
    print("AROUND PRAGUE")
    print("=" * 72)

    start = max(
        0,
        prague_index - 15
    )

    end = min(
        len(entries),
        prague_index + 16
    )

    for index in range(start, end):

        marker = (
            " <== PRAGUE"
            if index == prague_index
            else ""
        )

        print(
            f"{index:5d} / "
            f"{index + 1:5d}  "
            f"{entries[index]['key']}"
            f"{marker}"
        )
