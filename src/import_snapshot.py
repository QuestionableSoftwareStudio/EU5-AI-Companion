from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


snapshot_path = Path(sys.argv[1])
db_path = Path(sys.argv[2])

with snapshot_path.open("r", encoding="utf-8") as f:
    state = json.load(f)

campaign = state["campaign"]
player = state["player_country"]
locations = state["owned_locations"]
markets = state["markets"]


def compact(obj):
    return json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_date(value):
    y, m, d = map(int, value.split("."))
    return f"{y:04d}-{m:02d}-{d:02d}"


db_path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON")

conn.executescript("""
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    game_date TEXT NOT NULL,
    player_country_id INTEGER NOT NULL,
    player_tag TEXT,
    game_version TEXT,
    scope TEXT NOT NULL,
    source_path TEXT,
    created_at TEXT NOT NULL,

    UNIQUE(game_date, player_country_id, scope)
);

CREATE TABLE IF NOT EXISTS countries (
    snapshot_id INTEGER NOT NULL,
    country_id INTEGER NOT NULL,
    tag TEXT,

    gold REAL,
    income REAL,
    expense REAL,
    population REAL,
    great_power INTEGER,
    great_power_rank INTEGER,

    payload_json TEXT NOT NULL,

    PRIMARY KEY(snapshot_id, country_id),

    FOREIGN KEY(snapshot_id)
        REFERENCES snapshots(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS locations (
    snapshot_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,

    owner_id INTEGER,
    controller_id INTEGER,
    market_id INTEGER,
    province_id INTEGER,

    raw_material TEXT,
    development REAL,
    market_access REAL,
    tax REAL,

    payload_json TEXT NOT NULL,

    PRIMARY KEY(snapshot_id, location_id),

    FOREIGN KEY(snapshot_id)
        REFERENCES snapshots(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS markets (
    snapshot_id INTEGER NOT NULL,
    market_id INTEGER NOT NULL,

    center_location_id INTEGER,
    population REAL,
    capacity REAL,
    food REAL,

    payload_json TEXT NOT NULL,

    PRIMARY KEY(snapshot_id, market_id),

    FOREIGN KEY(snapshot_id)
        REFERENCES snapshots(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS market_goods (
    snapshot_id INTEGER NOT NULL,
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

    PRIMARY KEY(snapshot_id, market_id, good),

    FOREIGN KEY(snapshot_id)
        REFERENCES snapshots(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date
    ON snapshots(game_date);

CREATE INDEX IF NOT EXISTS idx_locations_market
    ON locations(snapshot_id, market_id);

CREATE INDEX IF NOT EXISTS idx_market_goods_good
    ON market_goods(good, snapshot_id);
""")


game_date = normalize_date(campaign["date"])
country_id = int(campaign["player_country_id"])

conn.execute("""
INSERT INTO snapshots (
    game_date,
    player_country_id,
    player_tag,
    game_version,
    scope,
    source_path,
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(game_date, player_country_id, scope)
DO UPDATE SET
    player_tag = excluded.player_tag,
    game_version = excluded.game_version,
    source_path = excluded.source_path,
    created_at = excluded.created_at
""", (
    game_date,
    country_id,
    campaign.get("player_tag"),
    campaign.get("version"),
    "player_slice",
    str(snapshot_path),
    datetime.now(timezone.utc).isoformat(),
))

snapshot_id = conn.execute("""
SELECT id
FROM snapshots
WHERE game_date = ?
  AND player_country_id = ?
  AND scope = ?
""", (
    game_date,
    country_id,
    "player_slice",
)).fetchone()[0]


# Safe re-import of the same snapshot.
conn.execute(
    "DELETE FROM market_goods WHERE snapshot_id = ?",
    (snapshot_id,),
)
conn.execute(
    "DELETE FROM markets WHERE snapshot_id = ?",
    (snapshot_id,),
)
conn.execute(
    "DELETE FROM locations WHERE snapshot_id = ?",
    (snapshot_id,),
)
conn.execute(
    "DELETE FROM countries WHERE snapshot_id = ?",
    (snapshot_id,),
)


currency = player.get("currency_data", {})
economy = player.get("economy", {})

conn.execute("""
INSERT INTO countries (
    snapshot_id,
    country_id,
    tag,
    gold,
    income,
    expense,
    population,
    great_power,
    great_power_rank,
    payload_json
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    snapshot_id,
    country_id,
    campaign.get("player_tag"),
    currency.get("gold"),
    economy.get("income"),
    economy.get("expense"),
    player.get("last_months_population"),
    int(bool(player.get("great_power"))),
    player.get("great_power_rank"),
    compact(player),
))


for location_id, loc in locations.items():
    conn.execute("""
    INSERT INTO locations (
        snapshot_id,
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
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot_id,
        int(location_id),
        loc.get("owner"),
        loc.get("controller"),
        loc.get("market"),
        loc.get("province"),
        loc.get("raw_material"),
        loc.get("development"),
        loc.get("market_access"),
        loc.get("tax"),
        compact(loc),
    ))


for market_id, market in markets.items():
    market_id_int = int(market_id)

    conn.execute("""
    INSERT INTO markets (
        snapshot_id,
        market_id,
        center_location_id,
        population,
        capacity,
        food,
        payload_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot_id,
        market_id_int,
        market.get("center"),
        market.get("population"),
        market.get("capacity"),
        market.get("food"),
        compact(market),
    ))

    for good, data in market.get("goods", {}).items():
        conn.execute("""
        INSERT INTO market_goods (
            snapshot_id,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id,
            market_id_int,
            good,
            data.get("price"),
            data.get("supply"),
            data.get("demand"),
            data.get("surplus"),
            data.get("stockpile"),
            int(bool(data.get("import"))),
            int(bool(data.get("export"))),
            compact(data),
        ))


conn.commit()

counts = {
    "countries": conn.execute(
        "SELECT COUNT(*) FROM countries WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()[0],

    "locations": conn.execute(
        "SELECT COUNT(*) FROM locations WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()[0],

    "markets": conn.execute(
        "SELECT COUNT(*) FROM markets WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()[0],

    "market_goods": conn.execute(
        "SELECT COUNT(*) FROM market_goods WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()[0],
}

print("SNAPSHOT IMPORTED")
print("=" * 60)
print("Snapshot id: ", snapshot_id)
print("Game date:   ", game_date)
print("Scope:        player_slice")
print("Countries:   ", counts["countries"])
print("Locations:   ", counts["locations"])
print("Markets:     ", counts["markets"])
print("Market goods:", counts["market_goods"])
print("Database:    ", db_path)
print(
    "DB size:     ",
    f"{db_path.stat().st_size / 1024 / 1024:.2f} MB"
)

conn.close()
