from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import sys
import time

import ijson

from visibility import VisibleLocations
from fast_save_lookup import read_played_country_id, read_visibility_ranges


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: stream_visible_world_to_db.py "
        "DECODED_JSON CAMPAIGN_DB"
    )


source = Path(sys.argv[1]).resolve()
db_path = Path(sys.argv[2]).resolve()

started = time.perf_counter()


# ============================================================
# Helpers
# ============================================================

def compact(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def bool_int(value):
    if value is None:
        return None

    return int(bool(value))


def normalize_date(value):
    if value is None:
        return None

    if isinstance(value, str):
        parts = value.split(".")

        if len(parts) == 3:
            y, m, d = map(
                int,
                parts,
            )

            return (
                f"{y:04d}-"
                f"{m:02d}-"
                f"{d:02d}"
            )

    return str(value)


def first_item(prefix):
    with source.open("rb") as f:

        iterator = ijson.items(
            f,
            prefix,
            use_float=True,
        )

        return next(
            iterator,
            None,
        )


def read_kv(prefix):
    with source.open("rb") as f:

        return dict(
            ijson.kvitems(
                f,
                prefix,
                use_float=True,
            )
        )


def hash_state(
    game_date,
    player_id,
    player_tag,
    countries,
    locations,
    markets,
    goods,
):
    """
    Deterministic hash of the complete retained visible slice.

    This replaces hashing the old 34 MB intermediate JSON.
    """

    h = hashlib.sha256()

    def add(value):
        if not isinstance(value, bytes):
            value = str(value).encode(
                "utf-8"
            )

        h.update(value)
        h.update(b"\0")

    add("EU5_VISIBLE_WORLD_V2")
    add(game_date)
    add(player_id)
    add(player_tag or "")

    for row in sorted(
        countries,
        key=lambda r: r[0],
    ):
        add("C")
        add(row[0])
        add(row[-1])

    for row in sorted(
        locations,
        key=lambda r: r[0],
    ):
        add("L")
        add(row[0])
        add(row[-1])

    for row in sorted(
        markets,
        key=lambda r: r[0],
    ):
        add("M")
        add(row[0])
        add(row[-1])

    for row in sorted(
        goods,
        key=lambda r: (
            r[0],
            r[1],
        ),
    ):
        add("G")
        add(row[0])
        add(row[1])
        add(row[-1])

    return h.hexdigest()


# ============================================================
# Schema
# ============================================================

def ensure_schema(conn):

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS current_meta (
        singleton INTEGER PRIMARY KEY
            CHECK(singleton = 1),

        game_date TEXT NOT NULL,

        player_country_id INTEGER NOT NULL,
        player_tag TEXT,

        game_version TEXT,

        captured_at TEXT NOT NULL,
        state_hash TEXT NOT NULL,

        visible_locations INTEGER NOT NULL,
        visible_countries INTEGER NOT NULL,
        visible_markets INTEGER NOT NULL
    );


    CREATE TABLE IF NOT EXISTS current_countries (
        country_id INTEGER PRIMARY KEY,

        tag TEXT,
        country_name TEXT,

        capital_location_id INTEGER,

        gold REAL,
        income REAL,
        expense REAL,
        population REAL,

        great_power INTEGER,
        great_power_rank INTEGER,

        payload_json TEXT NOT NULL
    );


    CREATE TABLE IF NOT EXISTS current_locations (
        location_id INTEGER PRIMARY KEY,

        owner_id INTEGER,
        controller_id INTEGER,

        market_id INTEGER,
        province_id INTEGER,

        raw_material TEXT,

        development REAL,
        market_access REAL,
        tax REAL,

        payload_json TEXT NOT NULL
    );


    CREATE TABLE IF NOT EXISTS current_markets (
        market_id INTEGER PRIMARY KEY,

        center_location_id INTEGER,

        population REAL,
        capacity REAL,

        food REAL,
        max_food REAL,

        price REAL,

        language TEXT,
        dialect TEXT,

        payload_json TEXT NOT NULL
    );


    CREATE TABLE IF NOT EXISTS current_market_goods (
        market_id INTEGER NOT NULL,
        good TEXT NOT NULL,

        price REAL,
        supply REAL,
        demand REAL,
        surplus REAL,
        stockpile REAL,

        is_import INTEGER,
        is_export INTEGER,

        payload_json TEXT NOT NULL,

        PRIMARY KEY(
            market_id,
            good
        )
    );


    CREATE TABLE IF NOT EXISTS captures (
        id INTEGER PRIMARY KEY,

        game_date TEXT NOT NULL,

        player_country_id INTEGER NOT NULL,
        player_tag TEXT,

        game_version TEXT,

        captured_at TEXT NOT NULL,

        state_hash TEXT NOT NULL UNIQUE,

        visible_locations INTEGER NOT NULL,
        visible_countries INTEGER NOT NULL,
        visible_markets INTEGER NOT NULL
    );


    CREATE TABLE IF NOT EXISTS history_country_metrics (
        capture_id INTEGER NOT NULL,
        country_id INTEGER NOT NULL,

        tag TEXT,
        country_name TEXT,

        capital_location_id INTEGER,

        gold REAL,
        income REAL,
        expense REAL,
        population REAL,

        great_power INTEGER,
        great_power_rank INTEGER,

        PRIMARY KEY(
            capture_id,
            country_id
        ),

        FOREIGN KEY(capture_id)
            REFERENCES captures(id)
            ON DELETE CASCADE
    );


    CREATE TABLE IF NOT EXISTS history_location_metrics (
        capture_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,

        owner_id INTEGER,
        controller_id INTEGER,

        market_id INTEGER,
        province_id INTEGER,

        raw_material TEXT,

        development REAL,
        market_access REAL,
        tax REAL,

        PRIMARY KEY(
            capture_id,
            location_id
        ),

        FOREIGN KEY(capture_id)
            REFERENCES captures(id)
            ON DELETE CASCADE
    );


    CREATE TABLE IF NOT EXISTS history_market_metrics (
        capture_id INTEGER NOT NULL,
        market_id INTEGER NOT NULL,

        center_location_id INTEGER,

        population REAL,
        capacity REAL,

        food REAL,
        max_food REAL,

        price REAL,

        PRIMARY KEY(
            capture_id,
            market_id
        ),

        FOREIGN KEY(capture_id)
            REFERENCES captures(id)
            ON DELETE CASCADE
    );


    CREATE TABLE IF NOT EXISTS history_market_goods (
        capture_id INTEGER NOT NULL,
        market_id INTEGER NOT NULL,
        good TEXT NOT NULL,

        price REAL,
        supply REAL,
        demand REAL,
        surplus REAL,
        stockpile REAL,

        is_import INTEGER,
        is_export INTEGER,

        PRIMARY KEY(
            capture_id,
            market_id,
            good
        ),

        FOREIGN KEY(capture_id)
            REFERENCES captures(id)
            ON DELETE CASCADE
    );


    CREATE INDEX IF NOT EXISTS
        idx_current_countries_tag
    ON current_countries(tag);


    CREATE INDEX IF NOT EXISTS
        idx_current_locations_owner
    ON current_locations(owner_id);


    CREATE INDEX IF NOT EXISTS
        idx_current_locations_market
    ON current_locations(market_id);


    CREATE INDEX IF NOT EXISTS
        idx_current_locations_raw
    ON current_locations(raw_material);


    CREATE INDEX IF NOT EXISTS
        idx_current_goods_good
    ON current_market_goods(good);


    CREATE INDEX IF NOT EXISTS
        idx_history_goods_good
    ON history_market_goods(
        good,
        capture_id
    );


    CREATE INDEX IF NOT EXISTS
        idx_history_locations_owner
    ON history_location_metrics(
        owner_id,
        capture_id
    );


    CREATE INDEX IF NOT EXISTS
        idx_captures_date
    ON captures(game_date);
    """)

    # Migration support for the earlier schema.
    columns = {
        row[1]
        for row in conn.execute(
            """
            PRAGMA table_info(
                history_country_metrics
            )
            """
        )
    }

    if "country_name" not in columns:

        conn.execute("""
            ALTER TABLE
                history_country_metrics
            ADD COLUMN
                country_name TEXT
        """)


# ============================================================
# Read campaign identity + visibility
# ============================================================

print("EU5 DIRECT VISIBLE-WORLD IMPORT")
print("=" * 70)


prep_started = time.perf_counter()


metadata = (
    first_item("metadata")
    or {}
)

raw_date = first_item(
    "start_of_day"
)

game_date = normalize_date(
    raw_date
)


flag = str(
    metadata.get(
        "flag",
        "",
    )
)

flag_match = re.match(
    r"\s*([A-Za-z0-9_]+)\s*=",
    flag,
)

if flag_match is None:
    raise RuntimeError(
        "Could not determine player tag "
        "from metadata.flag"
    )


player_tag = (
    flag_match.group(1)
)


player_lookup_started = time.perf_counter()

player_id = read_played_country_id(
    source
)

player_lookup_elapsed = (
    time.perf_counter()
    - player_lookup_started
)


visibility_started = time.perf_counter()

visibility_encoding = read_visibility_ranges(
    source,
    player_id,
)

visibility_lookup_elapsed = (
    time.perf_counter()
    - visibility_started
)


visible = VisibleLocations(
    visibility_encoding
)


prep_elapsed = (
    time.perf_counter()
    - prep_started
)


print(
    f"Player:            "
    f"{player_tag} ({player_id})"
)

print(
    f"Game date:         "
    f"{raw_date}"
)

print(
    f"Visible locations: "
    f"{visible.count()}"
)

print(
    f"Player-ID lookup:  "
    f"{player_lookup_elapsed:.2f}s"
)

print(
    f"Visibility lookup: "
    f"{visibility_lookup_elapsed:.2f}s"
)

print(
    f"Identity/visibility:"
    f" {prep_elapsed:.2f}s"
)


# ============================================================
# Visible locations
# ============================================================

print()
print(
    "[1/3] Reading visible locations..."
)


stage_started = (
    time.perf_counter()
)


location_current = []
location_history = []

visible_country_ids = set()
visible_market_ids = set()


with source.open("rb") as f:

    for location_id, loc in (
        ijson.kvitems(
            f,
            "locations.locations",
            use_float=True,
        )
    ):

        lid = int(
            location_id
        )

        if lid not in visible:
            continue


        owner_id = loc.get(
            "owner"
        )

        controller_id = loc.get(
            "controller"
        )

        market_id = loc.get(
            "market"
        )


        for cid in (
            owner_id,
            controller_id,
        ):
            if (
                isinstance(cid, int)
                and cid > 0
            ):
                visible_country_ids.add(
                    cid
                )


        if (
            isinstance(market_id, int)
            and market_id >= 0
        ):
            visible_market_ids.add(
                market_id
            )


        row = (
            lid,
            owner_id,
            controller_id,
            market_id,
            loc.get(
                "province"
            ),
            loc.get(
                "raw_material"
            ),
            loc.get(
                "development"
            ),
            loc.get(
                "market_access"
            ),
            loc.get(
                "tax"
            ),
        )


        location_history.append(
            row
        )

        location_current.append(
            row + (
                compact(loc),
            )
        )


locations_elapsed = (
    time.perf_counter()
    - stage_started
)


print(
    f"      Locations: "
    f"{len(location_current)}"
)

print(
    f"      Countries referenced: "
    f"{len(visible_country_ids)}"
)

print(
    f"      Markets referenced: "
    f"{len(visible_market_ids)}"
)

print(
    f"      Time: "
    f"{locations_elapsed:.2f}s"
)


# ============================================================
# Countries
# ============================================================

print()
print(
    "[2/3] Reading visible countries..."
)


stage_started = (
    time.perf_counter()
)


country_current = []
country_history = []

remaining_countries = set(
    visible_country_ids
)


with source.open("rb") as f:

    for country_id, country in (
        ijson.kvitems(
            f,
            "countries.database",
            use_float=True,
        )
    ):

        cid = int(
            country_id
        )

        if cid not in remaining_countries:
            continue


        tag = country.get(
            "flag"
        )

        if isinstance(tag, str):

            tag_match = re.match(
                r"\\s*([A-Za-z0-9_]+)"
                r"(?:\\s*=|$)",
                tag,
            )

            if tag_match is not None:
                tag = tag_match.group(1)

        else:
            tag = None

        if not tag:

            definition = country.get(
                "definition"
            )

            if isinstance(
                definition,
                str,
            ):
                tag = definition

        raw_country_name = country.get(
            "country_name"
        )

        if isinstance(
            raw_country_name,
            str,
        ):

            country_name = raw_country_name

        elif isinstance(
            raw_country_name,
            dict,
        ):

            nested_name = raw_country_name.get(
                "name"
            )

            country_name = (
                nested_name
                if isinstance(
                    nested_name,
                    str,
                )
                else None
            )

        else:

            country_name = None


        if (
            not tag
            and country_name
        ):
            tag = country_name


        currency = country.get(
            "currency_data",
            {}
        )

        economy = country.get(
            "economy",
            {}
        )


        row = (
            cid,
            tag,
            country_name,
            country.get(
                "capital"
            ),
            currency.get(
                "gold"
            ),
            economy.get(
                "income"
            ),
            economy.get(
                "expense"
            ),
            country.get(
                "last_months_population"
            ),
            bool_int(
                country.get(
                    "great_power"
                )
            ),
            country.get(
                "great_power_rank"
            ),
        )


        country_history.append(
            row
        )

        country_current.append(
            row + (
                compact(country),
            )
        )


        remaining_countries.remove(
            cid
        )

        if not remaining_countries:
            break


countries_elapsed = (
    time.perf_counter()
    - stage_started
)


print(
    f"      Countries: "
    f"{len(country_current)}"
)

print(
    f"      Time: "
    f"{countries_elapsed:.2f}s"
)


if remaining_countries:
    print(
        f"      Warning: "
        f"{len(remaining_countries)} "
        f"referenced countries not found"
    )


# ============================================================
# Markets + goods
# ============================================================

print()
print(
    "[3/3] Reading visible markets..."
)


stage_started = (
    time.perf_counter()
)


market_current = []
market_history = []

goods_current = []
goods_history = []

remaining_markets = set(
    visible_market_ids
)


with source.open("rb") as f:

    for market_id, market in (
        ijson.kvitems(
            f,
            "market_manager.database",
            use_float=True,
        )
    ):

        mid = int(
            market_id
        )

        if mid not in remaining_markets:
            continue


        market_row = (
            mid,
            market.get(
                "center"
            ),
            market.get(
                "population"
            ),
            market.get(
                "capacity"
            ),
            market.get(
                "food"
            ),
            market.get(
                "max"
            ),
            market.get(
                "price"
            ),
            market.get(
                "language"
            ),
            market.get(
                "dialect"
            ),
        )


        market_history.append(
            (
                mid,
                market.get(
                    "center"
                ),
                market.get(
                    "population"
                ),
                market.get(
                    "capacity"
                ),
                market.get(
                    "food"
                ),
                market.get(
                    "max"
                ),
                market.get(
                    "price"
                ),
            )
        )


        market_current.append(
            market_row + (
                compact(market),
            )
        )


        for good, data in (
            market.get(
                "goods",
                {}
            ).items()
        ):

            good_row = (
                mid,
                good,
                data.get(
                    "price"
                ),
                data.get(
                    "supply"
                ),
                data.get(
                    "demand"
                ),
                data.get(
                    "surplus"
                ),
                data.get(
                    "stockpile"
                ),
                bool_int(
                    data.get(
                        "import"
                    )
                ),
                bool_int(
                    data.get(
                        "export"
                    )
                ),
            )


            goods_history.append(
                good_row
            )

            goods_current.append(
                good_row + (
                    compact(data),
                )
            )


        remaining_markets.remove(
            mid
        )

        if not remaining_markets:
            break


markets_elapsed = (
    time.perf_counter()
    - stage_started
)


print(
    f"      Markets: "
    f"{len(market_current)}"
)

print(
    f"      Market goods: "
    f"{len(goods_current)}"
)

print(
    f"      Time: "
    f"{markets_elapsed:.2f}s"
)


if remaining_markets:
    print(
        f"      Warning: "
        f"{len(remaining_markets)} "
        f"referenced markets not found"
    )


# ============================================================
# State hash
# ============================================================

state_hash = hash_state(
    game_date,
    player_id,
    player_tag,
    country_current,
    location_current,
    market_current,
    goods_current,
)


# ============================================================
# SQLite
# ============================================================

print()
print(
    "Writing campaign database..."
)


db_started = (
    time.perf_counter()
)


db_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)


conn = sqlite3.connect(
    db_path
)

conn.execute(
    "PRAGMA foreign_keys = ON"
)

conn.execute(
    "PRAGMA journal_mode = WAL"
)

conn.execute(
    "PRAGMA synchronous = NORMAL"
)


ensure_schema(
    conn
)


captured_at = datetime.now(
    timezone.utc
).isoformat()


with conn:

    existing = conn.execute(
        """
        SELECT id
        FROM captures
        WHERE state_hash = ?
        """,
        (
            state_hash,
        ),
    ).fetchone()


    if existing is not None:

        capture_id = existing[0]
        history_is_new = False

    else:

        cursor = conn.execute(
            """
            INSERT INTO captures (
                game_date,
                player_country_id,
                player_tag,
                game_version,
                captured_at,
                state_hash,
                visible_locations,
                visible_countries,
                visible_markets
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                game_date,
                player_id,
                player_tag,
                metadata.get(
                    "version"
                ),
                captured_at,
                state_hash,
                len(location_current),
                len(country_current),
                len(market_current),
            ),
        )


        capture_id = (
            cursor.lastrowid
        )

        history_is_new = True


    # --------------------------------------------------------
    # Replace CURRENT atomically
    # --------------------------------------------------------

    conn.execute(
        "DELETE FROM current_market_goods"
    )

    conn.execute(
        "DELETE FROM current_markets"
    )

    conn.execute(
        "DELETE FROM current_locations"
    )

    conn.execute(
        "DELETE FROM current_countries"
    )

    conn.execute(
        "DELETE FROM current_meta"
    )


    conn.executemany(
        """
        INSERT INTO current_countries (
            country_id,
            tag,
            country_name,
            capital_location_id,
            gold,
            income,
            expense,
            population,
            great_power,
            great_power_rank,
            payload_json
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        country_current,
    )


    conn.executemany(
        """
        INSERT INTO current_locations (
            location_id,
            owner_id,
            controller_id,
            market_id,
            province_id,
            raw_material,
            development,
            market_access,
            tax,
            payload_json
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        location_current,
    )


    conn.executemany(
        """
        INSERT INTO current_markets (
            market_id,
            center_location_id,
            population,
            capacity,
            food,
            max_food,
            price,
            language,
            dialect,
            payload_json
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        market_current,
    )


    conn.executemany(
        """
        INSERT INTO current_market_goods (
            market_id,
            good,
            price,
            supply,
            demand,
            surplus,
            stockpile,
            is_import,
            is_export,
            payload_json
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        goods_current,
    )


    conn.execute(
        """
        INSERT INTO current_meta (
            singleton,
            game_date,
            player_country_id,
            player_tag,
            game_version,
            captured_at,
            state_hash,
            visible_locations,
            visible_countries,
            visible_markets
        )
        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            game_date,
            player_id,
            player_tag,
            metadata.get(
                "version"
            ),
            captured_at,
            state_hash,
            len(location_current),
            len(country_current),
            len(market_current),
        ),
    )


    # --------------------------------------------------------
    # Compact history only for genuinely new state
    # --------------------------------------------------------

    if history_is_new:

        conn.executemany(
            """
            INSERT INTO history_country_metrics (
                capture_id,
                country_id,
                tag,
                country_name,
                capital_location_id,
                gold,
                income,
                expense,
                population,
                great_power,
                great_power_rank
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                (
                    capture_id,
                ) + row

                for row
                in country_history
            ),
        )


        conn.executemany(
            """
            INSERT INTO history_location_metrics (
                capture_id,
                location_id,
                owner_id,
                controller_id,
                market_id,
                province_id,
                raw_material,
                development,
                market_access,
                tax
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                (
                    capture_id,
                ) + row

                for row
                in location_history
            ),
        )


        conn.executemany(
            """
            INSERT INTO history_market_metrics (
                capture_id,
                market_id,
                center_location_id,
                population,
                capacity,
                food,
                max_food,
                price
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                (
                    capture_id,
                ) + row

                for row
                in market_history
            ),
        )


        conn.executemany(
            """
            INSERT INTO history_market_goods (
                capture_id,
                market_id,
                good,
                price,
                supply,
                demand,
                surplus,
                stockpile,
                is_import,
                is_export
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                (
                    capture_id,
                ) + row

                for row
                in goods_history
            ),
        )


db_elapsed = (
    time.perf_counter()
    - db_started
)


capture_count = conn.execute(
    """
    SELECT COUNT(*)
    FROM captures
    """
).fetchone()[0]


conn.close()


# ============================================================
# Done
# ============================================================

elapsed = (
    time.perf_counter()
    - started
)


print()
print("=" * 70)
print("DIRECT VISIBLE WORLD READY")
print("=" * 70)

print(
    f"Game date:         "
    f"{game_date}"
)

print(
    f"Capture ID:        "
    f"{capture_id}"
)

print(
    f"New history:       "
    f"{history_is_new}"
)

print(
    f"Countries:         "
    f"{len(country_current)}"
)

print(
    f"Locations:         "
    f"{len(location_current)}"
)

print(
    f"Markets:           "
    f"{len(market_current)}"
)

print(
    f"Market goods:      "
    f"{len(goods_current)}"
)

print(
    f"History captures:  "
    f"{capture_count}"
)

print()
print(
    f"Identity/visibility:"
    f" {prep_elapsed:.2f}s"
)

print(
    f"Locations scan:    "
    f" {locations_elapsed:.2f}s"
)

print(
    f"Countries scan:    "
    f" {countries_elapsed:.2f}s"
)

print(
    f"Markets scan:      "
    f" {markets_elapsed:.2f}s"
)

print(
    f"Database write:    "
    f" {db_elapsed:.2f}s"
)

print(
    f"Total import:      "
    f" {elapsed:.2f}s"
)

print(
    f"Database size:     "
    f" {db_path.stat().st_size / 1024 / 1024:.2f} MB"
)
