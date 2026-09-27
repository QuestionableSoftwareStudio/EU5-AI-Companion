from __future__ import annotations

from runtime_paths import CAMPAIGN_DB, SNAPSHOT_DIR, TEMP_EU5_DIR, UV_CACHE_DIR, initialize_runtime

import json
import os
from pathlib import Path
import subprocess
import sys
import time


if len(sys.argv) != 4:
    raise SystemExit(
        "Usage: refresh_campaign.py RAKALY SAVE_FILE PROJECT_ROOT"
    )

rakaly = Path(sys.argv[1]).resolve()
save = Path(sys.argv[2]).resolve()
project = Path(sys.argv[3]).resolve()

if not rakaly.exists():
    raise SystemExit(f"Rakaly not found: {rakaly}")

if not save.exists():
    raise SystemExit(f"Save not found: {save}")


initialize_runtime()

temp_dir = TEMP_EU5_DIR
snapshot_dir = SNAPSHOT_DIR
db_path = CAMPAIGN_DB

temp_dir.mkdir(parents=True, exist_ok=True)
snapshot_dir.mkdir(parents=True, exist_ok=True)

decoded = temp_dir / "decoded_current.json"
temp_snapshot = temp_dir / "snapshot_current.json"

extract_script = project / "src" / "extract_player_state.py"
import_script = project / "src" / "import_snapshot.py"

env = os.environ.copy()

# Keep child-process temporary files away from C:
env["TEMP"] = str(temp_dir)
env["TMP"] = str(temp_dir)
env["UV_CACHE_DIR"] = str(UV_CACHE_DIR)


def run_python(script: Path, *args: str):
    result = subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        raise SystemExit(result.returncode)

    return result.stdout


total_started = time.perf_counter()

print("EU5 COMPANION REFRESH")
print("=" * 60)
print(f"Source save: {save}")
print()

try:
    # --------------------------------------------------------
    # 1. Decode native EU5 save -> transient UTF-8 JSON
    # --------------------------------------------------------

    print("[1/3] Decoding save...")

    started = time.perf_counter()

    with decoded.open("wb") as f:
        result = subprocess.run(
            [str(rakaly), "json", str(save)],
            stdout=f,
            stderr=subprocess.PIPE,
            env=env,
        )

    if result.returncode != 0:
        print(
            result.stderr.decode(errors="replace"),
            file=sys.stderr
        )
        raise SystemExit(result.returncode)

    decode_seconds = time.perf_counter() - started
    decoded_mb = decoded.stat().st_size / 1024 / 1024

    print(
        f"      {decode_seconds:.2f}s, "
        f"{decoded_mb:.2f} MB transient"
    )

    # --------------------------------------------------------
    # 2. Extract player-state snapshot
    # --------------------------------------------------------

    print("[2/3] Extracting structured state...")

    started = time.perf_counter()

    run_python(
        extract_script,
        decoded,
        temp_snapshot,
    )

    extract_seconds = time.perf_counter() - started

    with temp_snapshot.open("r", encoding="utf-8") as f:
        state = json.load(f)

    campaign = state["campaign"]

    game_date = campaign["date"]
    tag = campaign["player_tag"] or "UNKNOWN"

    date_filename = game_date.replace(".", "_")

    final_snapshot = (
        snapshot_dir /
        f"{tag}_{date_filename}.json"
    )

    # Replace same-date snapshot if refreshing it.
    temp_snapshot.replace(final_snapshot)

    snapshot_mb = final_snapshot.stat().st_size / 1024 / 1024

    print(
        f"      {extract_seconds:.2f}s, "
        f"{snapshot_mb:.2f} MB retained"
    )
    print(f"      {tag} @ {game_date}")

    # --------------------------------------------------------
    # 3. Import into SQLite history
    # --------------------------------------------------------

    print("[3/3] Updating campaign database...")

    started = time.perf_counter()

    import_output = run_python(
        import_script,
        final_snapshot,
        db_path,
    )

    import_seconds = time.perf_counter() - started

    print(f"      {import_seconds:.2f}s")

    total_seconds = time.perf_counter() - total_started

    print()
    print("=" * 60)
    print("REFRESH COMPLETE")
    print("=" * 60)
    print(f"Game date:       {game_date}")
    print(f"Country:         {tag}")
    print(f"Snapshot:        {final_snapshot}")
    print(f"Database:        {db_path}")
    print(
        f"Database size:   "
        f"{db_path.stat().st_size / 1024 / 1024:.2f} MB"
    )
    print(f"Total time:      {total_seconds:.2f}s")

    print()
    print("Database import:")
    print(import_output.strip())

finally:
    # Full decoded JSON is only a transient transport format.
    # Always reclaim it.
    if decoded.exists():
        decoded.unlink()

    if temp_snapshot.exists():
        temp_snapshot.unlink()
