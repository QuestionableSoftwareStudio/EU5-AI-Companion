from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class WorldState:
    def __init__(
        self,
        db_path: str | Path,
        static_db_path: str | Path | None = None,
    ):
        self.db_path = Path(db_path)

        if static_db_path is None:
            static_db_path = (
                self.db_path.parent
                / "static_data.db"
            )

        self.static_db_path = Path(
            static_db_path
        )

        self.has_static_data = (
            self.static_db_path.exists()
        )

    # ========================================================
    # Connection
    # ========================================================

    def connect(self):
        conn = sqlite3.connect(
            self.db_path
        )

        conn.row_factory = sqlite3.Row

        if self.has_static_data:
            conn.execute(
                "ATTACH DATABASE ? AS static",
                (
                    str(
                        self.static_db_path
                    ),
                ),
            )

        return conn

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _dict(row):
        if row is None:
            return None

        return dict(row)

    @staticmethod
    def _without_payload(row):
        if row is None:
            return None

        result = dict(row)

        result.pop(
            "payload_json",
            None,
        )

        return result

    @staticmethod
    def _with_payload(row):
        if row is None:
            return None

        result = dict(row)

        payload = result.pop(
            "payload_json",
            None,
        )

        if payload is not None:
            result["payload"] = (
                json.loads(payload)
            )

        return result

    @staticmethod
    def _normalize_flags(result):
        if result is None:
            return None

        for key in (
            "is_import",
            "is_export",
        ):
            if key in result:
                result[key] = bool(
                    result[key]
                )

        return result

    @staticmethod
    def _add_market_display_name(
        result,
    ):
        if result is None:
            return None

        center_name = result.get(
            "center_name"
        )

        if center_name:
            result["market_name"] = (
                f"{center_name} Market"
            )
        else:
            result["market_name"] = (
                f"Market "
                f"{result.get('market_id')}"
            )

        return result

    # ========================================================
    # Static-data helpers
    # ========================================================

    def get_location_name(
        self,
        location_id: int,
    ):
        if not self.has_static_data:
            return None

        with self.connect() as conn:
            row = conn.execute("""
                SELECT name
                FROM static.locations
                WHERE runtime_id = ?
            """, (
                location_id,
            )).fetchone()

        if row is None:
            return None

        return row["name"]

    def get_localized(
        self,
        key: str,
    ):
        if not self.has_static_data:
            return None

        with self.connect() as conn:
            row = conn.execute("""
                SELECT value
                FROM static.localization
                WHERE key = ?
            """, (
                key,
            )).fetchone()

        if row is None:
            return None

        return row["value"]

    # ========================================================
    # Goods key resolution
    # ========================================================

    def resolve_good_key(
        self,
        value: str,
    ):
        """
        Accept things such as:

            iron
            fine_cloth
            "Fine Cloth"
            "fine cloth"

        and resolve them to the internal good key.
        """

        raw = value.strip()

        candidates = [
            raw,
            raw.lower(),
            raw.lower().replace(
                " ",
                "_",
            ),
        ]

        with self.connect() as conn:

            for candidate in candidates:

                row = conn.execute("""
                    SELECT good
                    FROM current_market_goods
                    WHERE LOWER(good) = LOWER(?)
                    LIMIT 1
                """, (
                    candidate,
                )).fetchone()

                if row is not None:
                    return row["good"]

            if self.has_static_data:

                row = conn.execute("""
                    SELECT
                        l.key
                    FROM static.localization l
                    WHERE LOWER(l.value) = LOWER(?)
                      AND EXISTS (
                          SELECT 1
                          FROM current_market_goods g
                          WHERE g.good = l.key
                      )
                    LIMIT 1
                """, (
                    raw,
                )).fetchone()

                if row is not None:
                    return row["key"]

        return raw

    # ========================================================
    # Campaign
    # ========================================================

    def get_campaign_state(
        self,
    ) -> dict[str, Any] | None:

        with self.connect() as conn:
            row = conn.execute("""
                SELECT *
                FROM current_meta
                WHERE singleton = 1
            """).fetchone()

        result = self._dict(row)

        if result is not None:
            result["static_data"] = (
                self.has_static_data
            )

        return result

    # ========================================================
    # Countries
    # ========================================================

    def get_country(
        self,
        country: int | str,
        full: bool = False,
    ):
        with self.connect() as conn:

            if self.has_static_data:

                select_sql = """
                    SELECT
                        c.*,

                        COALESCE(
                            country_loc.value,
                            c.country_name,
                            c.tag
                        ) AS name,

                        capital_loc.name
                            AS capital_name

                    FROM current_countries c

                    LEFT JOIN static.localization
                        country_loc
                        ON country_loc.key = c.tag

                    LEFT JOIN static.locations
                        capital_loc
                        ON capital_loc.runtime_id
                            = c.capital_location_id
                """

            else:

                select_sql = """
                    SELECT
                        c.*,
                        COALESCE(
                            c.country_name,
                            c.tag
                        ) AS name,
                        NULL AS capital_name
                    FROM current_countries c
                """

            if (
                isinstance(country, int)
                or str(country).isdigit()
            ):

                row = conn.execute(
                    select_sql + """
                    WHERE c.country_id = ?
                    LIMIT 1
                    """,
                    (
                        int(country),
                    ),
                ).fetchone()

            else:

                row = conn.execute(
                    select_sql + """
                    WHERE UPPER(c.tag)
                        = UPPER(?)
                    LIMIT 1
                    """,
                    (
                        str(country),
                    ),
                ).fetchone()

        if full:
            return self._with_payload(
                row
            )

        return self._without_payload(
            row
        )

    def get_player_country(
        self,
        full: bool = False,
    ):
        meta = self.get_campaign_state()

        if meta is None:
            return None

        return self.get_country(
            meta[
                "player_country_id"
            ],
            full=full,
        )

    def get_country_locations(
        self,
        country: int | str,
    ):
        country_row = self.get_country(
            country
        )

        if country_row is None:
            return []

        country_id = (
            country_row["country_id"]
        )

        with self.connect() as conn:

            if self.has_static_data:

                rows = conn.execute("""
                    SELECT
                        l.location_id,

                        sl.name
                            AS location_name,

                        l.owner_id,
                        l.controller_id,
                        l.market_id,
                        l.province_id,

                        l.raw_material,

                        good_loc.value
                            AS raw_material_name,

                        l.development,
                        l.market_access,
                        l.tax

                    FROM current_locations l

                    LEFT JOIN static.locations sl
                        ON sl.runtime_id
                            = l.location_id

                    LEFT JOIN static.localization
                        good_loc
                        ON good_loc.key
                            = l.raw_material

                    WHERE l.owner_id = ?

                    ORDER BY l.location_id
                """, (
                    country_id,
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT
                        location_id,
                        owner_id,
                        controller_id,
                        market_id,
                        province_id,
                        raw_material,
                        development,
                        market_access,
                        tax
                    FROM current_locations
                    WHERE owner_id = ?
                    ORDER BY location_id
                """, (
                    country_id,
                )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def get_country_markets(
        self,
        country: int | str,
    ):
        country_row = self.get_country(
            country
        )

        if country_row is None:
            return []

        country_id = (
            country_row["country_id"]
        )

        with self.connect() as conn:

            if self.has_static_data:

                rows = conn.execute("""
                    SELECT DISTINCT
                        m.market_id,

                        m.center_location_id,

                        sl.name
                            AS center_name,

                        m.population,
                        m.capacity,

                        m.food,
                        m.max_food,

                        m.price,

                        m.language,
                        m.dialect

                    FROM current_locations l

                    JOIN current_markets m
                        ON m.market_id
                            = l.market_id

                    LEFT JOIN static.locations sl
                        ON sl.runtime_id
                            = m.center_location_id

                    WHERE l.owner_id = ?

                    ORDER BY m.market_id
                """, (
                    country_id,
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT DISTINCT
                        m.market_id,
                        m.center_location_id,
                        NULL AS center_name,
                        m.population,
                        m.capacity,
                        m.food,
                        m.max_food,
                        m.price,
                        m.language,
                        m.dialect
                    FROM current_locations l
                    JOIN current_markets m
                        ON m.market_id
                            = l.market_id
                    WHERE l.owner_id = ?
                    ORDER BY m.market_id
                """, (
                    country_id,
                )).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            self._add_market_display_name(
                item
            )

            result.append(item)

        return result

    # ========================================================
    # Locations
    # ========================================================

    def get_location(
        self,
        location_id: int,
        full: bool = False,
    ):
        with self.connect() as conn:

            if self.has_static_data:

                row = conn.execute("""
                    SELECT
                        l.*,

                        sl.key
                            AS location_key,

                        sl.name
                            AS location_name,

                        owner.tag
                            AS owner_tag,

                        owner_loc.value
                            AS owner_name,

                        controller.tag
                            AS controller_tag,

                        controller_loc.value
                            AS controller_name,

                        good_loc.value
                            AS raw_material_name

                    FROM current_locations l

                    LEFT JOIN static.locations sl
                        ON sl.runtime_id
                            = l.location_id

                    LEFT JOIN current_countries owner
                        ON owner.country_id
                            = l.owner_id

                    LEFT JOIN static.localization
                        owner_loc
                        ON owner_loc.key
                            = owner.tag

                    LEFT JOIN current_countries controller
                        ON controller.country_id
                            = l.controller_id

                    LEFT JOIN static.localization
                        controller_loc
                        ON controller_loc.key
                            = controller.tag

                    LEFT JOIN static.localization
                        good_loc
                        ON good_loc.key
                            = l.raw_material

                    WHERE l.location_id = ?
                """, (
                    location_id,
                )).fetchone()

            else:

                row = conn.execute("""
                    SELECT *
                    FROM current_locations
                    WHERE location_id = ?
                """, (
                    location_id,
                )).fetchone()

        if full:
            return self._with_payload(
                row
            )

        return self._without_payload(
            row
        )

    # ========================================================
    # Markets
    # ========================================================

    def get_market(
        self,
        market_id: int,
        full: bool = False,
    ):
        with self.connect() as conn:

            if self.has_static_data:

                row = conn.execute("""
                    SELECT
                        m.*,

                        sl.key
                            AS center_key,

                        sl.name
                            AS center_name

                    FROM current_markets m

                    LEFT JOIN static.locations sl
                        ON sl.runtime_id
                            = m.center_location_id

                    WHERE m.market_id = ?
                """, (
                    market_id,
                )).fetchone()

            else:

                row = conn.execute("""
                    SELECT
                        m.*,
                        NULL AS center_key,
                        NULL AS center_name
                    FROM current_markets m
                    WHERE m.market_id = ?
                """, (
                    market_id,
                )).fetchone()

        if full:
            result = self._with_payload(
                row
            )
        else:
            result = self._without_payload(
                row
            )

        return self._add_market_display_name(
            result
        )

    def get_market_good(
        self,
        market_id: int,
        good: str,
        full: bool = False,
    ):
        good_key = self.resolve_good_key(
            good
        )

        with self.connect() as conn:

            if self.has_static_data:

                row = conn.execute("""
                    SELECT
                        g.*,

                        loc.value
                            AS good_name

                    FROM current_market_goods g

                    LEFT JOIN static.localization loc
                        ON loc.key = g.good

                    WHERE g.market_id = ?
                      AND g.good = ?
                """, (
                    market_id,
                    good_key,
                )).fetchone()

            else:

                row = conn.execute("""
                    SELECT *
                    FROM current_market_goods
                    WHERE market_id = ?
                      AND good = ?
                """, (
                    market_id,
                    good_key,
                )).fetchone()

        if full:
            result = self._with_payload(
                row
            )
        else:
            result = self._without_payload(
                row
            )

        return self._normalize_flags(
            result
        )

    # ========================================================
    # Market analysis
    # ========================================================

    def get_market_shortages(
        self,
        market_id: int,
        limit: int = 20,
    ):
        with self.connect() as conn:

            if self.has_static_data:

                rows = conn.execute("""
                    SELECT
                        g.good,

                        loc.value
                            AS good_name,

                        g.price,
                        g.supply,
                        g.demand,
                        g.surplus,
                        g.stockpile,

                        g.is_import,
                        g.is_export,

                        (
                            COALESCE(
                                g.supply,
                                0
                            )
                            -
                            COALESCE(
                                g.demand,
                                0
                            )
                        ) AS balance

                    FROM current_market_goods g

                    LEFT JOIN static.localization loc
                        ON loc.key = g.good

                    WHERE g.market_id = ?

                      AND (
                          COALESCE(
                              g.supply,
                              0
                          )
                          -
                          COALESCE(
                              g.demand,
                              0
                          )
                      ) < 0

                    ORDER BY balance ASC

                    LIMIT ?
                """, (
                    market_id,
                    limit,
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT
                        good,
                        price,
                        supply,
                        demand,
                        surplus,
                        stockpile,
                        is_import,
                        is_export,

                        (
                            COALESCE(
                                supply,
                                0
                            )
                            -
                            COALESCE(
                                demand,
                                0
                            )
                        ) AS balance

                    FROM current_market_goods

                    WHERE market_id = ?

                      AND (
                          COALESCE(
                              supply,
                              0
                          )
                          -
                          COALESCE(
                              demand,
                              0
                          )
                      ) < 0

                    ORDER BY balance ASC

                    LIMIT ?
                """, (
                    market_id,
                    limit,
                )).fetchall()

        return [
            self._normalize_flags(
                dict(row)
            )
            for row in rows
        ]

    def get_market_surpluses(
        self,
        market_id: int,
        limit: int = 20,
    ):
        with self.connect() as conn:

            if self.has_static_data:

                rows = conn.execute("""
                    SELECT
                        g.good,

                        loc.value
                            AS good_name,

                        g.price,
                        g.supply,
                        g.demand,
                        g.surplus,
                        g.stockpile,

                        g.is_import,
                        g.is_export,

                        (
                            COALESCE(
                                g.supply,
                                0
                            )
                            -
                            COALESCE(
                                g.demand,
                                0
                            )
                        ) AS balance

                    FROM current_market_goods g

                    LEFT JOIN static.localization loc
                        ON loc.key = g.good

                    WHERE g.market_id = ?

                      AND (
                          COALESCE(
                              g.supply,
                              0
                          )
                          -
                          COALESCE(
                              g.demand,
                              0
                          )
                      ) > 0

                    ORDER BY balance DESC

                    LIMIT ?
                """, (
                    market_id,
                    limit,
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT
                        good,
                        price,
                        supply,
                        demand,
                        surplus,
                        stockpile,
                        is_import,
                        is_export,

                        (
                            COALESCE(
                                supply,
                                0
                            )
                            -
                            COALESCE(
                                demand,
                                0
                            )
                        ) AS balance

                    FROM current_market_goods

                    WHERE market_id = ?

                      AND (
                          COALESCE(
                              supply,
                              0
                          )
                          -
                          COALESCE(
                              demand,
                              0
                          )
                      ) > 0

                    ORDER BY balance DESC

                    LIMIT ?
                """, (
                    market_id,
                    limit,
                )).fetchall()

        return [
            self._normalize_flags(
                dict(row)
            )
            for row in rows
        ]

    # ========================================================
    # Goods across visible markets
    # ========================================================

    def get_good_worldwide(
        self,
        good: str,
        include_unknown: bool = False,
    ):
        good_key = self.resolve_good_key(
            good
        )

        with self.connect() as conn:

            if self.has_static_data:

                sql = """
                    SELECT
                        g.market_id,

                        m.center_location_id,

                        sl.name
                            AS center_name,

                        g.good,

                        good_loc.value
                            AS good_name,

                        g.price,
                        g.supply,
                        g.demand,
                        g.surplus,
                        g.stockpile,

                        g.is_import,
                        g.is_export

                    FROM current_market_goods g

                    JOIN current_markets m
                        ON m.market_id
                            = g.market_id

                    LEFT JOIN static.locations sl
                        ON sl.runtime_id
                            = m.center_location_id

                    LEFT JOIN static.localization
                        good_loc
                        ON good_loc.key
                            = g.good

                    WHERE g.good = ?
                """

            else:

                sql = """
                    SELECT
                        g.market_id,
                        m.center_location_id,
                        NULL AS center_name,
                        g.good,
                        NULL AS good_name,
                        g.price,
                        g.supply,
                        g.demand,
                        g.surplus,
                        g.stockpile,
                        g.is_import,
                        g.is_export
                    FROM current_market_goods g
                    JOIN current_markets m
                        ON m.market_id
                            = g.market_id
                    WHERE g.good = ?
                """

            params: list[Any] = [
                good_key
            ]

            if not include_unknown:
                sql += """
                    AND g.price IS NOT NULL
                """

            sql += """
                ORDER BY
                    g.price ASC,
                    g.market_id ASC
            """

            rows = conn.execute(
                sql,
                params,
            ).fetchall()

        result = []

        for row in rows:
            item = self._normalize_flags(
                dict(row)
            )

            self._add_market_display_name(
                item
            )

            result.append(item)

        return result

    # ========================================================
    # Raw-material producers
    # ========================================================

    def get_raw_material_producers(
        self,
        good: str,
        limit: int | None = None,
    ):
        good_key = self.resolve_good_key(
            good
        )

        with self.connect() as conn:

            if self.has_static_data:

                sql = """
                    SELECT
                        l.location_id,

                        sl.name
                            AS location_name,

                        l.owner_id,

                        c.tag
                            AS owner_tag,

                        country_loc.value
                            AS owner_name,

                        l.market_id,

                        l.raw_material,

                        good_loc.value
                            AS raw_material_name,

                        l.development,
                        l.market_access,
                        l.tax

                    FROM current_locations l

                    LEFT JOIN static.locations sl
                        ON sl.runtime_id
                            = l.location_id

                    LEFT JOIN current_countries c
                        ON c.country_id
                            = l.owner_id

                    LEFT JOIN static.localization
                        country_loc
                        ON country_loc.key
                            = c.tag

                    LEFT JOIN static.localization
                        good_loc
                        ON good_loc.key
                            = l.raw_material

                    WHERE l.raw_material = ?

                    ORDER BY
                        l.development DESC,
                        l.location_id
                """

            else:

                sql = """
                    SELECT
                        l.location_id,
                        NULL AS location_name,
                        l.owner_id,
                        c.tag AS owner_tag,
                        NULL AS owner_name,
                        l.market_id,
                        l.raw_material,
                        NULL AS raw_material_name,
                        l.development,
                        l.market_access,
                        l.tax
                    FROM current_locations l
                    LEFT JOIN current_countries c
                        ON c.country_id
                            = l.owner_id
                    WHERE l.raw_material = ?
                    ORDER BY
                        l.development DESC,
                        l.location_id
                """

            params: list[Any] = [
                good_key
            ]

            if limit is not None:
                sql += """
                    LIMIT ?
                """

                params.append(
                    limit
                )

            rows = conn.execute(
                sql,
                params,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # History
    # ========================================================

    def get_good_history(
        self,
        market_id: int,
        good: str,
    ):
        good_key = self.resolve_good_key(
            good
        )

        with self.connect() as conn:

            if self.has_static_data:

                rows = conn.execute("""
                    SELECT
                        c.game_date,
                        c.captured_at,

                        g.good,

                        loc.value
                            AS good_name,

                        g.price,
                        g.supply,
                        g.demand,
                        g.surplus,
                        g.stockpile,

                        g.is_import,
                        g.is_export

                    FROM history_market_goods g

                    JOIN captures c
                        ON c.id
                            = g.capture_id

                    LEFT JOIN static.localization loc
                        ON loc.key
                            = g.good

                    WHERE g.market_id = ?
                      AND g.good = ?

                    ORDER BY
                        c.game_date,
                        c.captured_at
                """, (
                    market_id,
                    good_key,
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT
                        c.game_date,
                        c.captured_at,
                        g.good,
                        g.price,
                        g.supply,
                        g.demand,
                        g.surplus,
                        g.stockpile,
                        g.is_import,
                        g.is_export
                    FROM history_market_goods g
                    JOIN captures c
                        ON c.id
                            = g.capture_id
                    WHERE g.market_id = ?
                      AND g.good = ?
                    ORDER BY
                        c.game_date,
                        c.captured_at
                """, (
                    market_id,
                    good_key,
                )).fetchall()

        return [
            self._normalize_flags(
                dict(row)
            )
            for row in rows
        ]
