from __future__ import annotations

import json
import mmap
from pathlib import Path


WHITESPACE = {
    ord(" "),
    ord("\t"),
    ord("\r"),
    ord("\n"),
}


def _skip_whitespace(
    mm: mmap.mmap,
    position: int,
):
    while (
        position < len(mm)
        and mm[position] in WHITESPACE
    ):
        position += 1

    return position


def _find_value_start(
    mm: mmap.mmap,
    key_position: int,
    key_length: int,
):
    colon = mm.find(
        b":",
        key_position + key_length,
    )

    if colon < 0:
        raise RuntimeError(
            "Malformed JSON: missing ':'"
        )

    return _skip_whitespace(
        mm,
        colon + 1,
    )


def _extract_container(
    mm: mmap.mmap,
    start: int,
):
    """
    Extract one JSON {...} or [...] value from an mmap.

    Handles nested containers and quoted strings.
    """

    if start >= len(mm):
        raise RuntimeError(
            "JSON value starts beyond EOF"
        )

    opening = mm[start]

    if opening == ord("{"):
        closing = ord("}")

    elif opening == ord("["):
        closing = ord("]")

    else:
        raise RuntimeError(
            "Expected JSON object or array"
        )

    depth = 0
    in_string = False
    escaped = False

    position = start

    while position < len(mm):

        char = mm[position]

        if escaped:
            escaped = False
            position += 1
            continue

        if (
            char == ord("\\")
            and in_string
        ):
            escaped = True
            position += 1
            continue

        if char == ord('"'):
            in_string = not in_string
            position += 1
            continue

        if in_string:
            position += 1
            continue

        if char == opening:
            depth += 1

        elif char == closing:
            depth -= 1

            if depth == 0:
                return mm[
                    start:
                    position + 1
                ]

        position += 1

    raise RuntimeError(
        "JSON container did not close"
    )


def read_played_country_id(
    json_path: str | Path,
):
    """
    Fast lookup of:

        played_country.country

    without parsing the hundreds-of-MB decoded save.
    """

    path = Path(json_path)

    with path.open("rb") as f:

        with mmap.mmap(
            f.fileno(),
            length=0,
            access=mmap.ACCESS_READ,
        ) as mm:

            key = b'"played_country"'

            position = mm.find(
                key
            )

            if position < 0:
                raise RuntimeError(
                    "played_country not found "
                    "in decoded save"
                )

            value_start = _find_value_start(
                mm,
                position,
                len(key),
            )

            raw_object = _extract_container(
                mm,
                value_start,
            )

    played_country = json.loads(
        raw_object
    )

    country_id = played_country.get(
        "country"
    )

    if country_id is None:
        raise RuntimeError(
            "played_country.country "
            "not found"
        )

    return int(country_id)


def read_visibility_ranges(
    json_path: str | Path,
    country_id: int,
):
    """
    Fast lookup for:

        terra_incognita
          -> countries
            -> COUNTRY_ID
              -> [
                   start, count,
                   start, count,
                   ...
                 ]

    Uses mmap native searching, then parses only the
    tiny visibility array.
    """

    path = Path(json_path)

    with path.open("rb") as f:

        with mmap.mmap(
            f.fileno(),
            length=0,
            access=mmap.ACCESS_READ,
        ) as mm:

            terra_key = (
                b'"terra_incognita"'
            )

            terra_position = mm.find(
                terra_key
            )

            if terra_position < 0:
                raise RuntimeError(
                    "terra_incognita not found"
                )


            countries_key = (
                b'"countries"'
            )

            countries_position = mm.find(
                countries_key,
                terra_position,
            )

            if countries_position < 0:
                raise RuntimeError(
                    "terra_incognita.countries "
                    "not found"
                )


            country_key = (
                f'"{country_id}"'
                .encode("ascii")
            )

            country_position = mm.find(
                country_key,
                countries_position,
            )

            if country_position < 0:
                raise RuntimeError(
                    "Visibility entry not found "
                    f"for country {country_id}"
                )


            value_start = _find_value_start(
                mm,
                country_position,
                len(country_key),
            )


            if (
                value_start >= len(mm)
                or mm[value_start]
                    != ord("[")
            ):
                raise RuntimeError(
                    "Visibility value is not "
                    "a JSON array"
                )


            raw_array = _extract_container(
                mm,
                value_start,
            )


    result = json.loads(
        raw_array
    )


    if not isinstance(
        result,
        list,
    ):
        raise RuntimeError(
            "Visibility data is not a list"
        )


    if len(result) % 2 != 0:
        raise RuntimeError(
            "Visibility RLE contains "
            "an odd number of values"
        )


    return result
