from __future__ import annotations

from pathlib import Path
import re
import sys


APP_VERSION = "0.1.6"

UPDATE_SCHEMA = 1
UPDATE_CHANNEL = "stable"

# Version of the launcher/update protocol rather than the app.
LAUNCHER_PROTOCOL = 1


_SEMVER = re.compile(
    r"^\d+\.\d+\.\d+$"
)


def get_app_version() -> str:
    """
    Return the version the user is actually running.

    Packaged self-updating builds live under:
        app/<version>/EU5 AI Companion App.exe

    Reading the version directory means a downloaded update can
    display its installed version even before source constants are
    changed for the next development cycle.

    Development/direct builds fall back to APP_VERSION.
    """

    if getattr(
        sys,
        "frozen",
        False,
    ):
        directory_name = (
            Path(sys.executable)
            .resolve()
            .parent
            .name
        )

        if _SEMVER.fullmatch(
            directory_name
        ):
            return directory_name

    return APP_VERSION
