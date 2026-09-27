from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import ijson

from eu5_pause_guard import (
    PauseGuardError,
    pause_for_snapshot,
)
from fast_save_lookup import (
    read_played_country_id,
)
from game_paths import (
    find_eu5_save_directory,
)


if len(sys.argv) != 4:
    raise SystemExit(
        "Usage: capture_core_state.py "
        "EU5_PID RAKALY PROJECT_ROOT"
    )


eu5_pid = int(
    sys.argv[1]
)

rakaly = Path(
    sys.argv[2]
).resolve()

project = Path(
    sys.argv[3]
).resolve()


save_dir = (
    find_eu5_save_directory()
)

if save_dir is None:
    raise SystemExit(
        "Could not find the Europa "
        "Universalis V save directory."
    )


live_save = (
    save_dir
    / "COMPANION_LIVE.eu5"
)

temp_dir = (
    project
    / ".temp"
    / "eu5_companion"
)

temp_dir.mkdir(
    parents=True,
    exist_ok=True,
)

decoded_file = (
    temp_dir
    / "decoded_current.json"
)

core_file = (
    temp_dir
    / "core_state.json"
)


SAVE_TIMEOUT = 30.0
POLL_INTERVAL = 0.25
STABLE_SECONDS = 1.0


def signature(
    path: Path,
):
    if not path.exists():
        return None

    stat = path.stat()

    return (
        stat.st_size,
        stat.st_mtime_ns,
    )


def wait_for_save_change(
    path: Path,
    old_signature,
):
    print(
        "Waiting for EU5 to write "
        "COMPANION_LIVE.eu5..."
    )

    deadline = (
        time.monotonic()
        + SAVE_TIMEOUT
    )

    changed_signature = None

    while time.monotonic() < deadline:

        current = signature(
            path
        )

        if (
            current is not None
            and current != old_signature
            and current[0] > 0
        ):
            changed_signature = current
            break

        time.sleep(
            POLL_INTERVAL
        )


    if changed_signature is None:
        raise TimeoutError(
            "EU5 did not update "
            "COMPANION_LIVE.eu5 "
            f"within {SAVE_TIMEOUT:.0f}s"
        )


    print(
        "Save changed. Waiting for "
        "file size/time to stabilize..."
    )

    stable_since = (
        time.monotonic()
    )

    previous = (
        changed_signature
    )


    while time.monotonic() < deadline:

        time.sleep(
            POLL_INTERVAL
        )

        current = signature(
            path
        )

        if current is None:
            stable_since = (
                time.monotonic()
            )
            continue


        if current == previous:

            if (
                time.monotonic()
                - stable_since
                >= STABLE_SECONDS
            ):
                return current

        else:

            previous = current

            stable_since = (
                time.monotonic()
            )


    raise TimeoutError(
        "COMPANION_LIVE.eu5 changed "
        "but did not stabilize in time"
    )


def first_item(
    source: Path,
    prefix: str,
):
    with source.open(
        "rb"
    ) as file:

        iterator = (
            ijson.items(
                file,
                prefix,
                use_float=True,
            )
        )

        return next(
            iterator,
            None,
        )


def normalize_date(
    value,
):
    if value is None:
        return None

    if isinstance(
        value,
        str,
    ):
        parts = (
            value.split(".")
        )

        if len(parts) == 3:

            try:
                year, month, day = map(
                    int,
                    parts,
                )

                return (
                    f"{year:04d}-"
                    f"{month:02d}-"
                    f"{day:02d}"
                )

            except ValueError:
                pass

    return str(
        value
    )


def extract_core_state(
    source: Path,
) -> dict:

    started = (
        time.perf_counter()
    )


    metadata = (
        first_item(
            source,
            "metadata",
        )
        or {}
    )

    raw_date = first_item(
        source,
        "start_of_day",
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

    if flag_match is not None:
        player_tag = (
            flag_match.group(1)
        )

    else:
        # Some saves may already expose the
        # plain tag rather than "TAG = {...}".
        plain_match = re.match(
            r"\s*([A-Za-z0-9_]+)",
            flag,
        )

        player_tag = (
            plain_match.group(1)
            if plain_match
            else None
        )


    player_id = (
        read_played_country_id(
            source
        )
    )


    player_country = None

    with source.open(
        "rb"
    ) as file:

        for country_id, country in (
            ijson.kvitems(
                file,
                "countries.database",
                use_float=True,
            )
        ):

            try:
                country_id_int = int(
                    country_id
                )

            except (
                TypeError,
                ValueError,
            ):
                continue


            if (
                country_id_int
                == player_id
            ):
                player_country = (
                    country
                )
                break


    if player_country is None:
        raise RuntimeError(
            "Could not find the player's "
            "country in countries.database."
        )


    currency = (
        player_country.get(
            "currency_data"
        )
        or {}
    )

    economy = (
        player_country.get(
            "economy"
        )
        or {}
    )


    raw_country_name = (
        player_country.get(
            "country_name"
        )
    )

    if isinstance(
        raw_country_name,
        str,
    ):
        country_name = (
            raw_country_name
        )

    else:
        country_name = (
            player_tag
        )


    income = economy.get(
        "income"
    )

    expense = economy.get(
        "expense"
    )

    income_minus_expense = None

    if (
        isinstance(
            income,
            (int, float),
        )
        and isinstance(
            expense,
            (int, float),
        )
    ):
        income_minus_expense = (
            income - expense
        )


    result = {
        "as_of": {
            "game_date": game_date,
            "exact_snapshot": True,
        },

        "player": {
            "country_id": player_id,
            "tag": player_tag,
            "name": country_name,

            "capital_location_id": (
                player_country.get(
                    "capital"
                )
            ),

            "gold": currency.get(
                "gold"
            ),

            "income": income,
            "expense": expense,

            "computed_income_minus_expense": (
                income_minus_expense
            ),

            "population": (
                player_country.get(
                    "last_months_population"
                )
            ),

            "great_power": bool(
                player_country.get(
                    "great_power"
                )
            ),

            "great_power_rank": (
                player_country.get(
                    "great_power_rank"
                )
            ),

            "stability": currency.get(
                "stability"
            ),

            "war_exhaustion": currency.get(
                "war_exhaustion"
            ),

            "prestige": currency.get(
                "prestige"
            ),

            "army_tradition": currency.get(
                "army_tradition"
            ),

            "government_power": (
                currency.get(
                    "government_power"
                )
            ),
        },
    }


    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"Fast core extraction: "
        f"{elapsed:.2f}s"
    )

    return result


print("=" * 70)
print("EU5 FAST CORE CAPTURE")
print("=" * 70)

print(
    f"EU5 PID: {eu5_pid}"
)

print(
    f"Target:  {live_save}"
)


overall_started = (
    time.perf_counter()
)

old_signature = signature(
    live_save
)


# ============================================================
# Fail closed if this script is ever run directly rather than
# through ask_eu5's already-confirmed pause.
# ============================================================

if (
    os.environ.get(
        "EU5_COMPANION_ALREADY_PAUSED"
    )
    != "1"
):

    print()
    print(
        "Checking campaign state..."
    )

    try:
        pause_for_snapshot(
            eu5_pid,
            project,
        )

    except PauseGuardError as exc:

        print()
        print(
            "LIVE CAPTURE CANCELLED"
        )

        print(
            str(exc)
        )

        raise SystemExit(20)


print()
print(
    "Requesting exact-date save "
    "from EU5 console..."
)


console_result = subprocess.run(
    [
        sys.executable,

        str(
            project
            / "src"
            / "send_eu5_console.py"
        ),

        str(
            eu5_pid
        ),

        "save COMPANION_LIVE",
    ],

    cwd=project,
)


if console_result.returncode != 0:
    raise RuntimeError(
        "Could not request "
        "COMPANION_LIVE save "
        f"(exit code "
        f"{console_result.returncode})."
    )


wait_for_save_change(
    live_save,
    old_signature,
)


print(
    f"Fresh save ready: "
    f"{live_save.stat().st_size / 1024 / 1024:.2f} MB"
)


# ============================================================
# Decode once.
#
# IMPORTANT:
# decoded_current.json deliberately remains on disk so a later
# market/good tool can import the full visible world from THIS
# SAME EXACT SNAPSHOT without asking EU5 for another save.
# ============================================================

print()
print(
    "Decoding exact snapshot..."
)

decode_started = (
    time.perf_counter()
)

decode_result = subprocess.run(
    [
        sys.executable,

        str(
            project
            / "src"
            / "decode_save.py"
        ),

        str(
            rakaly
        ),

        str(
            live_save
        ),

        str(
            decoded_file
        ),
    ],

    cwd=project,
)


if decode_result.returncode != 0:
    raise RuntimeError(
        "Rakaly decode failed "
        f"with exit code "
        f"{decode_result.returncode}"
    )


decode_elapsed = (
    time.perf_counter()
    - decode_started
)


core_state = (
    extract_core_state(
        decoded_file
    )
)


core_file.write_text(
    json.dumps(
        core_state,
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)


overall_elapsed = (
    time.perf_counter()
    - overall_started
)


print()
print("=" * 70)
print("FAST CORE STATE READY")
print("=" * 70)

print(
    f"Country:           "
    f"{core_state['player']['tag']}"
)

print(
    f"Game date:         "
    f"{core_state['as_of']['game_date']}"
)

print(
    f"Treasury:          "
    f"{core_state['player']['gold']}"
)

print(
    f"Decode:            "
    f"{decode_elapsed:.2f}s"
)

print(
    f"Total core capture:"
    f" {overall_elapsed:.2f}s"
)
