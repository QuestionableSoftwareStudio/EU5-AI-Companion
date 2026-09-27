from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import re
import sqlite3
import sys
import time


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: build_static_data.py EU5_ROOT STATIC_DB"
    )


root = Path(sys.argv[1]).resolve()
db_path = Path(sys.argv[2]).resolve()

game = root / "game"

templates_path = (
    game
    / "in_game"
    / "map_data"
    / "location_templates.txt"
)

definitions_path = (
    game
    / "in_game"
    / "map_data"
    / "definitions.txt"
)


for path in (
    templates_path,
    definitions_path,
):
    if not path.exists():
        raise SystemExit(
            f"Not found: {path}"
        )


started = time.perf_counter()


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


def sha256_file(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:

        while True:
            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


# ============================================================
# 1. Valid location keys
# ============================================================

print("EU5 STATIC DATA BUILDER")
print("=" * 70)

print("[1/5] Reading location templates...")


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

        line = strip_comment(
            raw_line
        )

        match = (
            template_pattern.match(
                line
            )
        )

        if not match:
            continue

        key = match.group(1)

        if key in location_key_set:
            continue

        location_keys.append(
            key
        )

        location_key_set.add(
            key
        )


print(
    f"      Valid locations: "
    f"{len(location_keys)}"
)


# ============================================================
# 2. Runtime location ID mapping
#
# Proven against all 50 visible market centers:
#
# runtime ID = first-occurrence position in definitions.txt + 1
# ============================================================

print(
    "[2/5] Building runtime location ID map..."
)


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

        line = strip_comment(
            raw_line
        )

        for token in (
            token_pattern.findall(
                line
            )
        ):

            if (
                token
                not in location_key_set
            ):
                continue

            if token in seen:
                continue

            seen.add(
                token
            )

            definition_order.append(
                token
            )


print(
    f"      Runtime locations: "
    f"{len(definition_order)}"
)


missing = (
    location_key_set
    - seen
)

if missing:
    print(
        f"      WARNING: "
        f"{len(missing)} location keys "
        f"not found in definitions.txt"
    )


# ============================================================
# 3. English localization
# ============================================================

print(
    "[3/5] Reading English localization..."
)


localization_files = []


for path in game.rglob("*.yml"):

    parts_lower = {
        part.lower()
        for part in path.parts
    }

    if "english" not in parts_lower:
        continue

    localization_files.append(
        path
    )


# Base files first, DLC afterwards so later content can override
# earlier localization keys.
def loc_priority(path: Path):

    relative = (
        path.relative_to(game)
    )

    parts = [
        p.lower()
        for p in relative.parts
    ]

    is_dlc = (
        1
        if "dlc" in parts
        else 0
    )

    return (
        is_dlc,
        str(relative).lower(),
    )


localization_files.sort(
    key=loc_priority
)


loc_pattern = re.compile(
    r'^\s*([^:#\s]+)\s*:\s*'
    r'(?:\d+\s+)?'
    r'"(.*)"\s*$'
)


localization = {}
localization_source = {}


for file in localization_files:

    try:

        with file.open(
            "r",
            encoding="utf-8-sig",
            errors="ignore",
        ) as f:

            for line_number, raw_line in enumerate(
                f,
                start=1,
            ):

                line = strip_comment(
                    raw_line
                )

                match = (
                    loc_pattern.match(
                        line
                    )
                )

                if not match:
                    continue

                key = match.group(1)
                value = match.group(2)

                localization[key] = (
                    value
                )

                localization_source[key] = (
                    f"{file}:{line_number}"
                )

    except OSError:
        continue


print(
    f"      English files: "
    f"{len(localization_files)}"
)

print(
    f"      Localization keys: "
    f"{len(localization)}"
)


# ============================================================
# 4. Build SQLite database
# ============================================================

print(
    "[4/5] Writing static database..."
)


db_path.parent.mkdir(
    parents=True,
    exist_ok=True
)


conn = sqlite3.connect(
    db_path
)

conn.execute(
    "PRAGMA journal_mode = WAL"
)

conn.execute(
    "PRAGMA synchronous = NORMAL"
)


conn.executescript("""
CREATE TABLE IF NOT EXISTS metadata (
    singleton INTEGER PRIMARY KEY
        CHECK(singleton = 1),

    built_at TEXT NOT NULL,

    eu5_root TEXT NOT NULL,

    definitions_hash TEXT NOT NULL,
    templates_hash TEXT NOT NULL,

    location_count INTEGER NOT NULL,
    localization_count INTEGER NOT NULL
);


CREATE TABLE IF NOT EXISTS localization (
    key TEXT PRIMARY KEY,

    value TEXT NOT NULL,

    source TEXT
);


CREATE TABLE IF NOT EXISTS locations (
    runtime_id INTEGER PRIMARY KEY,

    key TEXT NOT NULL UNIQUE,

    name TEXT
);


CREATE INDEX IF NOT EXISTS
    idx_locations_key
ON locations(key);


CREATE INDEX IF NOT EXISTS
    idx_locations_name
ON locations(name);
""")


location_rows = []


for index, key in enumerate(
    definition_order,
    start=1,
):

    name = localization.get(
        key
    )

    location_rows.append(
        (
            index,
            key,
            name,
        )
    )


built_at = datetime.now(
    timezone.utc
).isoformat()


with conn:

    conn.execute(
        "DELETE FROM metadata"
    )

    conn.execute(
        "DELETE FROM locations"
    )

    conn.execute(
        "DELETE FROM localization"
    )


    conn.executemany(
        """
        INSERT INTO localization (
            key,
            value,
            source
        )
        VALUES (?, ?, ?)
        """,
        (
            (
                key,
                value,
                localization_source.get(
                    key
                ),
            )
            for key, value
            in localization.items()
        ),
    )


    conn.executemany(
        """
        INSERT INTO locations (
            runtime_id,
            key,
            name
        )
        VALUES (?, ?, ?)
        """,
        location_rows,
    )


    conn.execute(
        """
        INSERT INTO metadata (
            singleton,
            built_at,
            eu5_root,
            definitions_hash,
            templates_hash,
            location_count,
            localization_count
        )
        VALUES (
            1, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            built_at,
            str(root),
            sha256_file(
                definitions_path
            ),
            sha256_file(
                templates_path
            ),
            len(definition_order),
            len(localization),
        ),
    )


# ============================================================
# 5. Verification
# ============================================================

print(
    "[5/5] Verifying known mappings..."
)


tests = {
    1: "stockholm",
    1515: "prague",
    1550: "london",
    2191: "paris",
    3291: "venice",
    4819: "moscow",
    5872: "constantinople",
}


failures = []


for runtime_id, expected_key in tests.items():

    row = conn.execute(
        """
        SELECT
            key,
            name
        FROM locations
        WHERE runtime_id = ?
        """,
        (
            runtime_id,
        ),
    ).fetchone()


    if row is None:

        failures.append(
            (
                runtime_id,
                expected_key,
                None,
            )
        )

        continue


    actual_key = row[0]

    if actual_key != expected_key:

        failures.append(
            (
                runtime_id,
                expected_key,
                actual_key,
            )
        )


# Extra useful lookups
prague = conn.execute(
    """
    SELECT
        runtime_id,
        key,
        name
    FROM locations
    WHERE runtime_id = 1515
    """
).fetchone()


bohemia = conn.execute(
    """
    SELECT value
    FROM localization
    WHERE key = 'BOH'
    """
).fetchone()


iron = conn.execute(
    """
    SELECT value
    FROM localization
    WHERE key = 'iron'
    """
).fetchone()


fine_cloth = conn.execute(
    """
    SELECT value
    FROM localization
    WHERE key = 'fine_cloth'
    """
).fetchone()


location_count = conn.execute(
    """
    SELECT COUNT(*)
    FROM locations
    """
).fetchone()[0]


localized_locations = conn.execute(
    """
    SELECT COUNT(*)
    FROM locations
    WHERE name IS NOT NULL
    """
).fetchone()[0]


conn.close()


elapsed = (
    time.perf_counter()
    - started
)


print()
print("=" * 70)


if failures:

    print(
        "STATIC DATA VERIFICATION FAILED"
    )

    for (
        runtime_id,
        expected,
        actual,
    ) in failures:

        print(
            f"ID {runtime_id}: "
            f"expected {expected}, "
            f"got {actual}"
        )

    raise SystemExit(1)


print(
    "STATIC DATA READY"
)

print("=" * 70)

print(
    f"Locations:           "
    f"{location_count}"
)

print(
    f"Localized locations: "
    f"{localized_locations}"
)

print(
    f"Localization keys:   "
    f"{len(localization)}"
)

print()

print(
    f"1515: "
    f"{prague[1]} -> "
    f"{prague[2]!r}"
)

print(
    f"BOH:  "
    f"{bohemia[0]!r}"
    if bohemia
    else "BOH: NOT LOCALIZED"
)

print(
    f"iron: "
    f"{iron[0]!r}"
    if iron
    else "iron: NOT LOCALIZED"
)

print(
    f"fine_cloth: "
    f"{fine_cloth[0]!r}"
    if fine_cloth
    else "fine_cloth: NOT LOCALIZED"
)

print()

print(
    f"Database size: "
    f"{db_path.stat().st_size / 1024 / 1024:.2f} MB"
)

print(
    f"Build time:    "
    f"{elapsed:.2f}s"
)

print(
    f"Database:      "
    f"{db_path}"
)
