from __future__ import annotations

from pathlib import Path
import re
import sys


if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: probe_game_names.py EU5_ROOT"
    )


root = Path(sys.argv[1]).resolve()
game = root / "game"

if not game.exists():
    raise SystemExit(
        f"Game data directory not found: {game}"
    )


print("=" * 70)
print("EU5 GAME-DATA NAME PROBE")
print("=" * 70)

print("Root:", root)
print("Game:", game)


# ============================================================
# Localization directories/files
# ============================================================

print()
print("=" * 70)
print("LOCALIZATION")
print("=" * 70)


loc_files = list(
    game.rglob("*.yml")
)

print(
    f"Localization .yml files found: "
    f"{len(loc_files)}"
)


loc_dirs = sorted({
    str(p.parent)
    for p in loc_files
})

print()
print("Localization directories:")

for directory in loc_dirs[:30]:
    print(" ", directory)

if len(loc_dirs) > 30:
    print(
        f"  ... +{len(loc_dirs) - 30} more"
    )


# ============================================================
# Parse a few localization keys we already know
# ============================================================

wanted_keys = {
    "BOH",
    "iron",
    "fish",
    "fine_cloth",
    "tools",
    "weaponry",
}

found_keys = {}


# Accept both:
#
# key: "Value"
# key:0 "Value"
#
loc_pattern = re.compile(
    r'^\s*([^:#\s]+)\s*:\s*'
    r'(?:\d+\s+)?'
    r'"(.*)"\s*$'
)


for file in loc_files:

    try:
        with file.open(
            "r",
            encoding="utf-8-sig",
            errors="ignore",
        ) as f:

            for line_number, line in enumerate(
                f,
                start=1,
            ):

                match = loc_pattern.match(line)

                if not match:
                    continue

                key = match.group(1)

                if key not in wanted_keys:
                    continue

                if key in found_keys:
                    continue

                found_keys[key] = {
                    "value": match.group(2),
                    "file": str(file),
                    "line": line_number,
                }

    except OSError:
        continue


print()
print("Known-key localization:")

for key in sorted(wanted_keys):

    result = found_keys.get(key)

    if result is None:
        print(
            f"  {key}: NOT FOUND"
        )

    else:
        print(
            f"  {key}: "
            f"{result['value']!r}"
        )

        print(
            f"      {result['file']}"
            f":{result['line']}"
        )


# ============================================================
# Locate country definition for BOH
# ============================================================

print()
print("=" * 70)
print("BOHEMIA DEFINITION CANDIDATES")
print("=" * 70)


text_extensions = {
    ".txt",
    ".csv",
    ".info",
    ".yml",
}


def text_files_under(path: Path):

    if not path.exists():
        return

    for file in path.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in text_extensions:
            continue

        yield file


country_dirs = [
    game / "in_game" / "setup" / "countries",
    game / "main_menu" / "setup" / "countries",
]


boh_matches = []


for directory in country_dirs:

    for file in text_files_under(directory):

        try:
            text = file.read_text(
                encoding="utf-8-sig",
                errors="ignore",
            )

        except OSError:
            continue

        if re.search(
            r"\bBOH\b",
            text,
            re.IGNORECASE,
        ):
            boh_matches.append(
                str(file)
            )


if not boh_matches:
    print("No BOH setup match found.")

else:
    for match in boh_matches[:30]:
        print(match)


# ============================================================
# Find how location ID 1515 is represented in game data
# ============================================================

print()
print("=" * 70)
print("LOCATION 1515")
print("=" * 70)


search_roots = [
    game / "in_game" / "map_data",
    game / "in_game" / "setup",
    game / "main_menu" / "setup",
]


needles = {
    "1515": re.compile(
        r"(?<!\d)1515(?!\d)"
    ),

    "prague": re.compile(
        r"prague",
        re.IGNORECASE,
    ),

    "praha": re.compile(
        r"praha",
        re.IGNORECASE,
    ),
}


matches = {
    key: []
    for key in needles
}


MAX_MATCHES_PER_NEEDLE = 30


for directory in search_roots:

    for file in text_files_under(directory):

        # Avoid repeatedly reading very large unrelated files.
        try:
            if file.stat().st_size > 100 * 1024 * 1024:
                continue
        except OSError:
            continue

        try:
            with file.open(
                "r",
                encoding="utf-8-sig",
                errors="ignore",
            ) as f:

                for line_number, line in enumerate(
                    f,
                    start=1,
                ):

                    for name, pattern in needles.items():

                        if (
                            len(matches[name])
                            >= MAX_MATCHES_PER_NEEDLE
                        ):
                            continue

                        if pattern.search(line):
                            matches[name].append(
                                (
                                    str(file),
                                    line_number,
                                    line.strip()[:500],
                                )
                            )

        except OSError:
            continue


for needle in (
    "1515",
    "prague",
    "praha",
):

    print()
    print(f"Search: {needle!r}")

    rows = matches[needle]

    if not rows:
        print("  NO MATCHES")
        continue

    for file, line_number, text in rows:
        print(
            f"  {file}:{line_number}"
        )
        print(
            f"    {text}"
        )


# ============================================================
# Candidate map/setup structure
# ============================================================

print()
print("=" * 70)
print("MAP-DATA FILES")
print("=" * 70)


map_data = (
    game
    / "in_game"
    / "map_data"
)

if not map_data.exists():
    print(
        f"Not found: {map_data}"
    )

else:
    files = [
        p
        for p in map_data.rglob("*")
        if p.is_file()
    ]

    print(
        f"Files: {len(files)}"
    )

    for file in files[:80]:
        print(
            file.relative_to(root)
        )

    if len(files) > 80:
        print(
            f"... +{len(files) - 80} more"
        )
