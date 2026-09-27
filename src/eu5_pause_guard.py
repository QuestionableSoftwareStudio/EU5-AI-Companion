from __future__ import annotations

from pathlib import Path
import subprocess
import sys


EVENT_ID = "eu5_companion.1"
EXPECTED = f"Fired event: {EVENT_ID}"


class PauseGuardError(RuntimeError):
    pass


def pause_for_snapshot(
    eu5_pid: int,
    project: Path,
    debug_log: Path | None = None,
) -> None:
    """
    Ask EU5 to fire the Companion pause event and require a
    positive acknowledgement from EU5's actual console output.

    If acknowledgement is not received, fail closed:
    the caller must NOT issue a save command.
    """

    helper = (
        project
        / "src"
        / "eu5_console_expect.py"
    )

    if not helper.exists():
        raise PauseGuardError(
            "EU5 console acknowledgement helper "
            "was not found."
        )

    print(
        "Requesting Companion pause event..."
    )

    result = subprocess.run(
        [
            sys.executable,
            str(helper),
            str(eu5_pid),
            EXPECTED,
            "event",
            EVENT_ID,
        ],
    )

    if result.returncode == 0:
        print(
            "EU5 confirmed Companion pause."
        )
        return

    if result.returncode == 20:
        raise PauseGuardError(
            "EU5 did not confirm the Companion "
            "pause event. No save was requested. "
            "Make sure a campaign is loaded and "
            "the EU5 AI Companion mod is enabled."
        )

    raise PauseGuardError(
        "Could not communicate with EU5's "
        f"console (exit code {result.returncode}). "
        "No save was requested."
    )
