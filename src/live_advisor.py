from __future__ import annotations

from runtime_paths import CAMPAIGN_DB, initialize_runtime

import json
from pathlib import Path
import subprocess
import sys
import time

from advisor_context import AdvisorContext
from world_state import WorldState


if len(sys.argv) < 6:
    raise SystemExit(
        """
Usage:

  live_advisor.py EU5_PID RAKALY PROJECT_ROOT market MARKET_ID

  live_advisor.py EU5_PID RAKALY PROJECT_ROOT good GOOD

Examples:

  live_advisor.py 12345 rakaly.exe PROJECT_ROOT market 23

  live_advisor.py 12345 rakaly.exe PROJECT_ROOT good "Fine Cloth"
""".strip()
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

command = sys.argv[4]

command_args = sys.argv[5:]

python = sys.executable

initialize_runtime()

db_path = CAMPAIGN_DB


# ============================================================
# 1. Refresh from the running game
# ============================================================

print("=" * 70)
print("EU5 COMPANION")
print("=" * 70)

print()
print("Fetching current game state...")

started = time.perf_counter()


result = subprocess.run(
    [
        python,
        str(
            project
            / "src"
            / "capture_live_state.py"
        ),
        str(eu5_pid),
        str(rakaly),
        str(project),
    ],
    cwd=project,
)


if result.returncode != 0:
    raise SystemExit(
        result.returncode
    )


refresh_elapsed = (
    time.perf_counter()
    - started
)


# ============================================================
# 2. Verify freshly imported state
# ============================================================

world = WorldState(
    db_path
)

state = (
    world.get_campaign_state()
)

if state is None:
    raise RuntimeError(
        "Live capture succeeded but "
        "campaign state is unavailable"
    )


print()
print("=" * 70)

print(
    f"LIVE — "
    f"{state['player_tag']} "
    f"{state['game_date']}"
)

print("=" * 70)


# ============================================================
# 3. Build intentionally exposed AI context
# ============================================================

advisor = AdvisorContext(
    str(db_path)
)


context_started = (
    time.perf_counter()
)


if command == "market":

    if len(command_args) != 1:
        raise SystemExit(
            "market requires MARKET_ID"
        )

    context = advisor.market_brief(
        int(
            command_args[0]
        )
    )


elif command == "good":

    if not command_args:
        raise SystemExit(
            "good requires GOOD"
        )

    good = " ".join(
        command_args
    )

    context = advisor.good_brief(
        good
    )


else:
    raise SystemExit(
        f"Unknown advisor command: "
        f"{command}"
    )


context_elapsed = (
    time.perf_counter()
    - context_started
)


# ============================================================
# 4. Output
# ============================================================

print()

print(
    json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
    )
)


total_elapsed = (
    time.perf_counter()
    - started
)


print()
print("=" * 70)

print(
    f"Fresh-state acquisition: "
    f"{refresh_elapsed:.2f}s"
)

print(
    f"Advisor context:         "
    f"{context_elapsed:.3f}s"
)

print(
    f"Total:                   "
    f"{total_elapsed:.2f}s"
)

print("=" * 70)
