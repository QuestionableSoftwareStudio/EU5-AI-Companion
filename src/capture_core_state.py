from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import ijson
from ijson.common import ObjectBuilder

from eu5_pause_guard import (
    PauseGuardError,
    pause_for_snapshot,
)
from game_paths import (
    find_eu5_save_directory,
)
from runtime_paths import (
    TEMP_EU5_DIR,
    initialize_runtime,
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

initialize_runtime()

decoded_file = (
    TEMP_EU5_DIR
    / "decoded_current.json"
)

core_file = (
    TEMP_EU5_DIR
    / "core_state.json"
)

player_country_file = (
    TEMP_EU5_DIR
    / "player_country.json"
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


def player_tag_from_flag(
    value,
):
    flag = str(
        value
        or ""
    )

    match = re.match(
        r"\s*([A-Za-z0-9_]+)\s*=",
        flag,
    )

    if match is not None:
        return match.group(1)

    match = re.match(
        r"\s*([A-Za-z0-9_]+)",
        flag,
    )

    return (
        match.group(1)
        if match
        else None
    )


def stream_player_state():
    """
    Stream Rakaly JSON and stop as soon as the exact player-country
    object has been captured.

    This avoids writing/parsing the hundreds-of-MB full decoded JSON
    for ordinary country-state questions. The full snapshot is decoded
    lazily later only if a market/world tool actually needs it.
    """

    started = (
        time.perf_counter()
    )

    process = subprocess.Popen(
        [
            str(
                rakaly
            ),
            "json",
            str(
                live_save
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if process.stdout is None:
        process.kill()
        raise RuntimeError(
            "Rakaly stdout pipe was not created."
        )

    raw_date = None
    player_tag = None
    player_id = None
    player_country = None

    builder = None
    capture_depth = 0
    target_prefix = None

    scalar_events = {
        "string",
        "number",
        "boolean",
        "null",
    }

    try:

        for prefix, event, value in ijson.parse(
            process.stdout,
            use_float=True,
        ):

            if (
                prefix == "start_of_day"
                and event in scalar_events
            ):
                raw_date = value


            if (
                prefix == "metadata.flag"
                and event in scalar_events
            ):
                player_tag = (
                    player_tag_from_flag(
                        value
                    )
                )


            if (
                player_id is None
                and player_tag
                and prefix.startswith(
                    "countries.tags."
                )
                and event in scalar_events
                and str(
                    value
                ) == player_tag
            ):
                raw_id = (
                    prefix.rsplit(
                        ".",
                        1,
                    )[-1]
                )

                try:
                    player_id = int(
                        raw_id
                    )

                except ValueError:
                    pass

                if player_id is not None:
                    target_prefix = (
                        "countries.database."
                        f"{player_id}"
                    )


            if (
                builder is None
                and target_prefix is not None
                and prefix == target_prefix
                and event == "start_map"
            ):
                builder = (
                    ObjectBuilder()
                )

                builder.event(
                    event,
                    value,
                )

                capture_depth = 1
                continue


            if builder is not None:

                builder.event(
                    event,
                    value,
                )

                if event in (
                    "start_map",
                    "start_array",
                ):
                    capture_depth += 1

                elif event in (
                    "end_map",
                    "end_array",
                ):
                    capture_depth -= 1


                if capture_depth == 0:
                    player_country = (
                        builder.value
                    )

                    builder = None

                    if raw_date is not None:
                        break


    finally:

        if (
            player_country is not None
            and process.poll() is None
        ):
            process.terminate()


        try:
            return_code = (
                process.wait(
                    timeout=5,
                )
            )

        except subprocess.TimeoutExpired:
            process.kill()
            return_code = (
                process.wait()
            )


        stderr_text = ""

        if process.stderr is not None:
            stderr_text = (
                process.stderr
                .read()
                .decode(
                    errors="replace"
                )
                .strip()
            )


    if player_country is None:

        detail = (
            f" Rakaly stderr: {stderr_text}"
            if stderr_text
            else ""
        )

        raise RuntimeError(
            "Could not stream the current "
            "player-country state from the save."
            + detail
        )


    if player_id is None:
        raise RuntimeError(
            "Could not identify the current "
            "player country ID."
        )


    if not player_tag:
        player_tag = str(
            player_country.get(
                "country_name",
                "",
            )
            or ""
        )


    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"Player-state stream: "
        f"{elapsed:.2f}s"
    )


    return (
        normalize_date(
            raw_date
        ),
        player_id,
        player_tag,
        player_country,
    )


def build_core_state(
    game_date,
    player_id,
    player_tag,
    player_country,
):

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

    country_name = (
        raw_country_name
        if isinstance(
            raw_country_name,
            str,
        )
        else player_tag
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
            (
                int,
                float,
            ),
        )
        and isinstance(
            expense,
            (
                int,
                float,
            ),
        )
    ):
        income_minus_expense = (
            income
            - expense
        )


    return {
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

        "_source_save": str(
            live_save
        ),
    }


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


# A stale full decode must never be mistaken for this new snapshot.
decoded_file.unlink(
    missing_ok=True
)

player_country_file.unlink(
    missing_ok=True
)


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
            str(
                exc
            )
        )

        raise SystemExit(
            20
        )


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


print()
print(
    "Reading exact player state..."
)


(
    game_date,
    player_id,
    player_tag,
    player_country,
) = stream_player_state()


core_state = build_core_state(
    game_date,
    player_id,
    player_tag,
    player_country,
)


player_country_file.write_text(
    json.dumps(
        player_country,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
    ),
    encoding="utf-8",
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
    f"Total core capture:"
    f" {overall_elapsed:.2f}s"
)
