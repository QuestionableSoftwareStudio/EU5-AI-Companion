from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import time


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: import_visible_world.py SNAPSHOT_JSON CAMPAIGN_DB"
    )

snapshot_path = Path(sys.argv[1])
db_path = Path(sys.argv[2])

started = time.perf_counter()


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
    y, m, d = map(int, value.split("."))

    return f"{y:04d}-{m:02d}-{d:02d}"


def sha256_file(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


# ============================================================
# Load snapshot
# ============================================================

print("EU5 VISIBLE WORLD IMPORT")
print("=" * 60)

print("[1/4] Loading snapshot...")

state_hash = sha256_file(snapshot_path)

with snapshot_path.open(
    "r",
    encoding="utf-8"
) as f:
    state = json.load(f)


campaign = state["campaign"]
countries = state["countries"]
country_tags = state.get(
    "country_tags",
    {}
)
locations = state["locations"]
markets = state["markets"]

game_date = normalize_date(
    campaign["date"]
)

captured_at = datetime.now(
    timezone.utc
).isoformat()


market_good_count = sum(
    len(
        market.get(
            "goods",
            {}
        )
    )
    for market in markets.values()
)


print(
    f"      Date:      {game_date}"
)
print(
    f"      Countries: {len(countries)}"
)
print(
    f"      Locations: {len(locations)}"
)
print(
    f"      Markets:   {len(markets)}"
)
print(
    f"      Goods:     {market_good_count}"
)


# ============================================================
# Database
# ============================================================

print("[2/4] Preparing database...")

db_path.parent.mkdir(
    parents=True,
    exist_ok=True
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


# ============================================================
# Schema
# ============================================================

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


CREATE INDEX IF NOT EXISTS idx_current_countries_tag
    ON current_countries(tag);


CREATE INDEX IF NOT EXISTS idx_current_locations_owner
    ON current_locations(owner_id);


CREATE INDEX IF NOT EXISTS idx_current_locations_market
    ON current_locations(market_id);


CREATE INDEX IF NOT EXISTS idx_current_locations_raw
    ON current_locations(raw_material);


CREATE INDEX IF NOT EXISTS idx_current_goods_good
    ON current_market_goods(good);


CREATE INDEX IF NOT EXISTS idx_history_goods_good
    ON history_market_goods(
        good,
        capture_id
    );


CREATE INDEX IF NOT EXISTS idx_history_locations_owner
    ON history_location_metrics(
        owner_id,
        capture_id
    );


CREATE INDEX IF NOT EXISTS idx_captures_date
    ON captures(game_date);
""")


# ============================================================
# Migration from the first broken schema
#
# The earlier version created history_country_metrics without
# country_name. CREATE TABLE IF NOT EXISTS won't modify an
# existing table, so add it automatically if necessary.
# ============================================================

history_country_columns = {
    row[1]
    for row in conn.execute(
        """
        PRAGMA table_info(
            history_country_metrics
        )
        """
    )
}

if (
    "country_name"
    not in history_country_columns
):
    print(
        "      Migrating "
        "history_country_metrics..."
    )

    conn.execute("""
        ALTER TABLE history_country_metrics
        ADD COLUMN country_name TEXT
    """)


# ============================================================
# Build batches
# ============================================================

print("[3/4] Building rows...")


# ------------------------------------------------------------
# Countries
# ------------------------------------------------------------

country_current = []
country_history = []


for country_id, country in countries.items():

    cid = int(country_id)

    economy = country.get(
        "economy",
        {}
    )

    currency = country.get(
        "currency_data",
        {}
    )

    tag = country_tags.get(
        country_id
    )

    row = (
        cid,
        tag,
        country.get(
            "country_name"
        ),
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

    country_current.append(
        row + (
            compact(country),
        )
    )

    country_history.append(
        row
    )


# ------------------------------------------------------------
# Locations
# ------------------------------------------------------------

location_current = []
location_history = []


for location_id, loc in locations.items():

    lid = int(location_id)

    row = (
        lid,
        loc.get(
            "owner"
        ),
        loc.get(
            "controller"
        ),
        loc.get(
            "market"
        ),
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

    location_current.append(
        row + (
            compact(loc),
        )
    )

    location_history.append(
        row
    )


# ------------------------------------------------------------
# Markets + goods
# ------------------------------------------------------------

market_current = []
market_history = []

goods_current = []
goods_history = []


for market_id, market in markets.items():

    mid = int(market_id)

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

    market_current.append(
        market_row + (
            compact(market),
        )
    )

    # History does not need language/dialect every capture.
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

    for good, data in market.get(
        "goods",
        {}
    ).items():

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

        goods_current.append(
            good_row + (
                compact(data),
            )
        )

        goods_history.append(
            good_row
        )


# ============================================================
# Write everything atomically
# ============================================================

print(
    "[4/4] Writing current state + history..."
)


with conn:

    # --------------------------------------------------------
    # Check whether this exact visible-world state has already
    # been inserted into history.
    # --------------------------------------------------------

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
                campaign[
                    "player_country_id"
                ],
                campaign.get(
                    "player_tag"
                ),
                campaign.get(
                    "version"
                ),
                captured_at,
                state_hash,
                len(locations),
                len(countries),
                len(markets),
            ),
        )

        capture_id = (
            cursor.lastrowid
        )

        history_is_new = True


    # ========================================================
    # CURRENT STATE
    #
    # Always replace completely.
    # ========================================================

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
            campaign[
                "player_country_id"
            ],
            campaign.get(
                "player_tag"
            ),
            campaign.get(
                "version"
            ),
            captured_at,
            state_hash,
            len(locations),
            len(countries),
            len(markets),
        ),
    )


    # ========================================================
    # HISTORY
    #
    # Append only when the state hash is new.
    # ========================================================

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


# ============================================================
# Verification
# ============================================================

counts = {
    "countries": conn.execute(
        """
        SELECT COUNT(*)
        FROM current_countries
        """
    ).fetchone()[0],

    "locations": conn.execute(
        """
        SELECT COUNT(*)
        FROM current_locations
        """
    ).fetchone()[0],

    "markets": conn.execute(
        """
        SELECT COUNT(*)
        FROM current_markets
        """
    ).fetchone()[0],

    "goods": conn.execute(
        """
        SELECT COUNT(*)
        FROM current_market_goods
        """
    ).fetchone()[0],

    "captures": conn.execute(
        """
        SELECT COUNT(*)
        FROM captures
        """
    ).fetchone()[0],

    "history_countries": conn.execute(
        """
        SELECT COUNT(*)
        FROM history_country_metrics
        WHERE capture_id = ?
        """,
        (
            capture_id,
        ),
    ).fetchone()[0],

    "history_locations": conn.execute(
        """
        SELECT COUNT(*)
        FROM history_location_metrics
        WHERE capture_id = ?
        """,
        (
            capture_id,
        ),
    ).fetchone()[0],

    "history_markets": conn.execute(
        """
        SELECT COUNT(*)
        FROM history_market_metrics
        WHERE capture_id = ?
        """,
        (
            capture_id,
        ),
    ).fetchone()[0],

    "history_goods": conn.execute(
        """
        SELECT COUNT(*)
        FROM history_market_goods
        WHERE capture_id = ?
        """,
        (
            capture_id,
        ),
    ).fetchone()[0],
}


conn.close()


elapsed = (
    time.perf_counter()
    - started
)


print()
print("=" * 60)
print("VISIBLE WORLD DATABASE READY")
print("=" * 60)

print(
    f"Game date:        {game_date}"
)

print(
    f"Capture ID:       {capture_id}"
)

print(
    f"New history:      {history_is_new}"
)

print(
    f"Countries:        {counts['countries']}"
)

print(
    f"Locations:        {counts['locations']}"
)

print(
    f"Markets:          {counts['markets']}"
)

print(
    f"Market goods:     {counts['goods']}"
)

print(
    f"History countries:{counts['history_countries']}"
)

print(
    f"History locations:{counts['history_locations']}"
)

print(
    f"History markets:  {counts['history_markets']}"
)

print(
    f"History goods:    {counts['history_goods']}"
)

print(
    f"History captures: {counts['captures']}"
)

print(
    f"Database size:    "
    f"{db_path.stat().st_size / 1024 / 1024:.2f} MB"
)

print(
    f"Import time:      {elapsed:.2f}s"
)

print(
    f"Database:         {db_path}"
)
