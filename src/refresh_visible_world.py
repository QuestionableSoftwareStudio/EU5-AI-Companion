from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from runtime_paths import (
    CAMPAIGN_DB,
    TEMP_EU5_DIR,
    initialize_runtime,
)


if len(sys.argv) != 4:
    raise SystemExit(
        "Usage: refresh_visible_world.py "
        "RAKALY SAVE_FILE PROJECT_ROOT"
    )


rakaly = Path(
    sys.argv[1]
).resolve()

save_file = Path(
    sys.argv[2]
).resolve()

project = Path(
    sys.argv[3]
).resolve()

python = sys.executable


initialize_runtime()


# ============================================================
# Temporary decoded save
#
# During development keep the ~311 MB Rakaly transport file
# on the project drive rather than filling C:.
#
# Frozen builds continue using the packaged runtime temp path.
# ============================================================

if getattr(
    sys,
    "frozen",
    False,
):

    temp_dir = TEMP_EU5_DIR

else:

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

db_file = CAMPAIGN_DB

hash_file = (
    db_file.parent
    / "decoded_snapshot.sha256"
)


def run_step(
    name: str,
    args: list[str],
):

    print()
    print(name)

    started = (
        time.perf_counter()
    )

    result = subprocess.run(
        args,
        cwd=project,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{name} failed "
            f"with exit code "
            f"{result.returncode}"
        )

    print(
        f"{name} completed "
        f"in {elapsed:.2f}s"
    )

    return elapsed


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def read_saved_hash():

    if not hash_file.exists():
        return None

    try:

        value = (
            hash_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
            .lower()
        )

        return (
            value
            if value
            else None
        )

    except OSError:
        return None


def write_saved_hash(
    value: str,
):

    hash_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_hash = (
        hash_file.parent
        / (
            hash_file.name
            + ".tmp"
        )
    )

    temp_hash.write_text(
        value + "\n",
        encoding="utf-8",
    )

    temp_hash.replace(
        hash_file
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

    except sqlite3.Error:
        return None

    finally:
        conn.close()


print("=" * 70)
print("EU5 VISIBLE WORLD REFRESH")
print("=" * 70)

print(
    f"Save:     {save_file}"
)

print(
    f"Database: {db_file}"
)

print(
    f"Temp:     {decoded_file}"
)


if not rakaly.exists():
    raise SystemExit(
        f"Rakaly not found: {rakaly}"
    )

if not save_file.exists():
    raise SystemExit(
        f"Save not found: {save_file}"
    )


overall_started = (
    time.perf_counter()
)


decode_time = None
hash_time = None
import_time = None

snapshot_reused = False
meta = None


try:

    # ========================================================
    # Rakaly decode
    # ========================================================

    decode_time = run_step(
        "[1/2] Decoding EU5 save...",
        [
            python,

            str(
                project
                / "src"
                / "decode_save.py"
            ),

            str(rakaly),
            str(save_file),
            str(decoded_file),
        ],
    )


    # ========================================================
    # Deterministic decoded snapshot fingerprint
    # ========================================================

    print()
    print(
        "Checking decoded snapshot hash..."
    )

    hash_started = (
        time.perf_counter()
    )

    current_hash = sha256_file(
        decoded_file
    )

    hash_time = (
        time.perf_counter()
        - hash_started
    )

    previous_hash = (
        read_saved_hash()
    )

    cached_meta = (
        read_current_meta()
    )


    snapshot_reused = (
        cached_meta is not None
        and previous_hash is not None
        and previous_hash
        == current_hash
    )


    if snapshot_reused:

        print(
            "Decoded snapshot unchanged."
        )

        print(
            "Reusing existing "
            "campaign database."
        )

        meta = cached_meta


    else:

        print(
            "Decoded snapshot changed."
        )

        # ====================================================
        # Direct visible-world extraction ? SQLite
        # ====================================================

        import_time = run_step(
            "[2/2] Updating visible-world database...",
            [
                python,

                str(
                    project
                    / "src"
                    / "stream_visible_world_to_db.py"
                ),

                str(decoded_file),
                str(db_file),
            ],
        )


        # ====================================================
        # Verification
        # ====================================================

        meta = read_current_meta()

        if meta is None:
            raise RuntimeError(
                "Refresh completed but "
                "current_meta is missing"
            )


        # Only trust/store the hash AFTER
        # the database import has succeeded.
        write_saved_hash(
            current_hash
        )


    if meta is None:
        raise RuntimeError(
            "No valid campaign metadata "
            "is available"
        )


    overall_elapsed = (
        time.perf_counter()
        - overall_started
    )


    print()
    print("=" * 70)
    print("VISIBLE WORLD LIVE STATE READY")
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

    print()

    print(
        f"Decode:            "
        f"{decode_time:.2f}s"
    )

    print(
        f"Hash check:        "
        f"{hash_time:.2f}s"
    )

    if snapshot_reused:

        print(
            "Direct import:     "
            "SKIPPED"
        )

    else:

        print(
            f"Direct import:     "
            f"{import_time:.2f}s"
        )

    print(
        f"Total refresh:     "
        f"{overall_elapsed:.2f}s"
    )


finally:

    # Decoded Rakaly JSON is transport only.
    try:

        if decoded_file.exists():

            decoded_file.unlink()

    except OSError as exc:

        print(
            f"Warning: could not delete "
            f"{decoded_file}: {exc}"
        )
