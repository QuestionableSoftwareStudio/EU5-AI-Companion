from __future__ import annotations


from runtime_paths import CAMPAIGN_DB, initialize_runtime

from pathlib import Path
import os
import sqlite3
import subprocess
import sys
import time

from game_paths import find_eu5_save_directory
from eu5_pause_guard import PauseGuardError, pause_for_snapshot


if len(sys.argv) != 4:
    raise SystemExit(
        "Usage: capture_live_state.py "
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


python = sys.executable


live_save = (
    save_dir
    / "COMPANION_LIVE.eu5"
)

initialize_runtime()

db_file = CAMPAIGN_DB

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


def read_current_meta():

    if not db_file.exists():
        return None

    conn = sqlite3.connect(
        db_file
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:

        row = conn.execute("""
            SELECT *
            FROM current_meta
            WHERE singleton = 1
        """).fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        conn.close()


print("=" * 70)
print("EU5 LIVE CAPTURE")
print("=" * 70)

print(
    f"EU5 PID: {eu5_pid}"
)

print(
    f"Target:  {live_save}"
)


old_signature = signature(
    live_save
)


if old_signature is None:

    print(
        "Previous save: none"
    )

else:

    print(
        f"Previous save: "
        f"{old_signature[0] / 1024 / 1024:.2f} MB"
    )


overall_started = (
    time.perf_counter()
)


# ============================================================
# Positively verify that a campaign is loaded and pause it.
#
# IMPORTANT:
# No save command is permitted until EU5 acknowledges that
# the Companion event was successfully fired.
# ============================================================

debug_log = (
    save_dir.parent
    / "logs"
    / "debug.log"
)

print()
print("Checking campaign state...")

if (
    os.environ.get(
        "EU5_COMPANION_ALREADY_PAUSED"
    )
    == "1"
):
    print(
        "Companion pause already confirmed "
        "by request router."
    )

else:
    try:
        pause_for_snapshot(
            eu5_pid,
            project,
            debug_log,
        )

    except PauseGuardError as exc:
        print()
        print("LIVE CAPTURE CANCELLED")
        print(str(exc))
        raise SystemExit(20)


# ============================================================
# Ask EU5 to create an exact-current-state save.
#
# This does NOT toggle pause.
# ============================================================

print()
print(
    "Requesting exact-date save "
    "from EU5 console..."
)


console_result = subprocess.run(
    [
        python,
        str(
            project
            / "src"
            / "send_eu5_console.py"
        ),
        str(eu5_pid),
        "save COMPANION_LIVE",
    ],
    cwd=project,
)


if console_result.returncode != 0:

    raise SystemExit(
        console_result.returncode
    )


# ============================================================
# Wait until save is actually complete
# ============================================================

new_signature = (
    wait_for_save_change(
        live_save,
        old_signature,
    )
)


print(
    f"Fresh save ready: "
    f"{new_signature[0] / 1024 / 1024:.2f} MB"
)


# ============================================================
# Decode → visible world → SQLite
# ============================================================

print()
print(
    "Refreshing visible-world database..."
)


refresh_result = subprocess.run(
    [
        python,
        str(
            project
            / "src"
            / "refresh_visible_world.py"
        ),
        str(rakaly),
        str(live_save),
        str(project),
    ],
    cwd=project,
)


if refresh_result.returncode != 0:

    raise SystemExit(
        refresh_result.returncode
    )



meta = read_current_meta()

if meta is None:

    raise RuntimeError(
        "Live refresh completed but "
        "campaign.db has no current_meta"
    )


elapsed = (
    time.perf_counter()
    - overall_started
)


print()
print("=" * 70)
print("LIVE STATE READY")
print("=" * 70)

print(
    f"Country:           "
    f"{meta['player_tag']}"
)

print(
    f"Game date:         "
    f"{meta['game_date']}"
)

print(
    f"Visible countries: "
    f"{meta['visible_countries']}"
)

print(
    f"Visible locations: "
    f"{meta['visible_locations']}"
)

print(
    f"Visible markets:   "
    f"{meta['visible_markets']}"
)

print(
    f"Captured from:     "
    f"{live_save.name}"
)

print(
    f"Total live capture:"
    f" {elapsed:.2f}s"
)
