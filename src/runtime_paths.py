from __future__ import annotations

import os
import shutil
import sys

from pathlib import Path


APP_NAME = "EU5 AI Companion"


def _application_root() -> Path:

    if getattr(
        sys,
        "frozen",
        False,
    ):
        return (
            Path(sys.executable)
            .resolve()
            .parent
        )

    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


def _local_appdata() -> Path:

    value = os.environ.get(
        "LOCALAPPDATA"
    )

    if value:
        return Path(value)

    return (
        Path.home()
        / "AppData"
        / "Local"
    )


APP_ROOT = _application_root()

RUNTIME_ROOT = (
    _local_appdata()
    / APP_NAME
)

DATA_DIR = (
    RUNTIME_ROOT
    / "data"
)

CACHE_DIR = (
    RUNTIME_ROOT
    / "cache"
)

TEMP_DIR = (
    RUNTIME_ROOT
    / "temp"
)

LOG_DIR = (
    RUNTIME_ROOT
    / "logs"
)

CONFIG_DIR = (
    RUNTIME_ROOT
    / "config"
)

UPDATE_DIR = (
    RUNTIME_ROOT
    / "updates"
)


CAMPAIGN_DB = (
    DATA_DIR
    / "campaign.db"
)

SNAPSHOT_DIR = (
    DATA_DIR
    / "snapshots"
)

TEMP_EU5_DIR = (
    TEMP_DIR
    / "eu5_companion"
)

UV_CACHE_DIR = (
    CACHE_DIR
    / "uv"
)

SAVE_METADATA_CACHE = (
    CACHE_DIR
    / "save_metadata.json"
)

GAME_PATHS_CONFIG = (
    CONFIG_DIR
    / "game_paths.json"
)

CONSOLE_LOG = (
    LOG_DIR
    / "console_bridge_test.txt"
)


# Application-owned resource.
# This gets replaced when the app updates.
STATIC_DB = (
    APP_ROOT
    / "data"
    / "static_data.db"
)


def ensure_runtime_dirs() -> None:

    for directory in (
        RUNTIME_ROOT,
        DATA_DIR,
        CACHE_DIR,
        TEMP_DIR,
        LOG_DIR,
        CONFIG_DIR,
        UPDATE_DIR,
        SNAPSHOT_DIR,
        TEMP_EU5_DIR,
        UV_CACHE_DIR,
    ):

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


def migrate_legacy_runtime_data(
) -> list[str]:
    """
    Development migration from the old layout.

    This deliberately does not migrate disposable
    temp/cache/log files.

    Packaged builds do not migrate application-folder
    files, preventing an accidentally bundled campaign.db
    from becoming user state.
    """

    ensure_runtime_dirs()

    messages = []


    if getattr(
        sys,
        "frozen",
        False,
    ):
        return messages


    # -----------------------------------------------------
    # Existing campaign database
    # -----------------------------------------------------

    old_campaign = (
        APP_ROOT
        / "data"
        / "campaign.db"
    )


    if (
        old_campaign.is_file()
        and not CAMPAIGN_DB.exists()
    ):

        shutil.copy2(
            old_campaign,
            CAMPAIGN_DB,
        )

        messages.append(
            "Migrated campaign.db"
        )


    # -----------------------------------------------------
    # Existing manually selected EU5 path
    # -----------------------------------------------------

    old_game_paths = (
        APP_ROOT
        / "data"
        / "game_paths.json"
    )


    if (
        old_game_paths.is_file()
        and not GAME_PATHS_CONFIG.exists()
    ):

        shutil.copy2(
            old_game_paths,
            GAME_PATHS_CONFIG,
        )

        messages.append(
            "Migrated game_paths.json"
        )


    return messages


def initialize_runtime() -> None:

    ensure_runtime_dirs()

    migrate_legacy_runtime_data()


if __name__ == "__main__":

    initialize_runtime()

    print(
        "Application root:"
    )
    print(
        " ",
        APP_ROOT,
    )

    print()
    print(
        "Runtime root:"
    )
    print(
        " ",
        RUNTIME_ROOT,
    )

    print()
    print(
        "Campaign DB:"
    )
    print(
        " ",
        CAMPAIGN_DB,
    )

    print()
    print(
        "Static DB:"
    )
    print(
        " ",
        STATIC_DB,
    )

    print()
    print(
        "Game paths config:"
    )
    print(
        " ",
        GAME_PATHS_CONFIG,
    )
