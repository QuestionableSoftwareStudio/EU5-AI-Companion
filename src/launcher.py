from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

from update_client import (
    download_package,
    fetch_manifest,
    install_package,
    is_newer,
    verify_package,
)


APP_NAME = "EU5 AI Companion"
APP_EXECUTABLE = (
    "EU5 AI Companion App.exe"
)

UPDATE_SCHEMA = 1
UPDATE_CHANNEL = "stable"
LAUNCHER_PROTOCOL = 1

DEFAULT_UPDATE_MANIFEST_URL = (
    "https://github.com/"
    "QuestionableSoftwareStudio/"
    "EU5-AI-Companion/"
    "releases/latest/download/"
    "update.json"
)

UPDATE_MANIFEST_URL = os.environ.get(
    "EU5_COMPANION_UPDATE_URL",
    DEFAULT_UPDATE_MANIFEST_URL,
).strip()


def install_root() -> Path:
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


def local_appdata() -> Path:
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


ROOT = install_root()

APP_DIR = (
    ROOT
    / "app"
)

CURRENT_FILE = (
    ROOT
    / "current.json"
)

UPDATE_CACHE = (
    local_appdata()
    / APP_NAME
    / "updates"
)

LAUNCHER_LOG = (
    UPDATE_CACHE
    / "launcher.log"
)

FAILED_UPDATE_FILE = (
    UPDATE_CACHE
    / "failed-update.json"
)


def log(message: str) -> None:
    UPDATE_CACHE.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LAUNCHER_LOG.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            message.rstrip()
            + "\n"
        )


def show_error(
    title: str,
    message: str,
) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            title,
            0x10,
        )

    except Exception:
        pass


def read_failed_update_version() -> str | None:
    if not FAILED_UPDATE_FILE.is_file():
        return None

    try:
        data = json.loads(
            FAILED_UPDATE_FILE.read_text(
                encoding="utf-8-sig"
            )
        )

        value = str(
            data.get(
                "version",
                "",
            )
        ).strip()

        return value or None

    except Exception as exc:
        log(
            "Could not read failed-update.json: "
            f"{exc}"
        )

        return None


def mark_failed_update(
    version: str,
) -> None:
    UPDATE_CACHE.mkdir(
        parents=True,
        exist_ok=True,
    )

    FAILED_UPDATE_FILE.write_text(
        json.dumps(
            {
                "version": version,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def read_current_version() -> str | None:
    if not CURRENT_FILE.is_file():
        return None

    try:
        data = json.loads(
            CURRENT_FILE.read_text(
                encoding="utf-8-sig"
            )
        )

        value = str(
            data.get(
                "version",
                "",
            )
        ).strip()

        return value or None

    except Exception as exc:
        log(
            "Could not read current.json: "
            f"{exc}"
        )

        return None


def write_current_version(
    version: str,
) -> None:
    temporary = (
        CURRENT_FILE
        .with_suffix(".json.tmp")
    )

    temporary.write_text(
        json.dumps(
            {
                "version": version,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(
        temporary,
        CURRENT_FILE,
    )


def executable_for(
    version: str,
) -> Path:
    return (
        APP_DIR
        / version
        / APP_EXECUTABLE
    )


def installed_versions() -> list[str]:
    if not APP_DIR.is_dir():
        return []

    versions = []

    for child in APP_DIR.iterdir():
        if not child.is_dir():
            continue

        if child.name.startswith("."):
            continue

        if (
            child
            / APP_EXECUTABLE
        ).is_file():
            versions.append(
                child.name
            )

    return versions


def choose_fallback_version(
) -> str | None:
    candidates = (
        installed_versions()
    )

    if not candidates:
        return None

    def key(value: str):
        try:
            return tuple(
                int(part)
                for part
                in value.split(".")
            )

        except Exception:
            return (-1, -1, -1)

    return max(
        candidates,
        key=key,
    )


def maybe_update(
    current_version: str | None,
) -> str | None:
    if (
        os.environ.get(
            "EU5_COMPANION_SKIP_UPDATE"
        )
        == "1"
    ):
        return current_version

    manifest = fetch_manifest(
        UPDATE_MANIFEST_URL
    )

    if manifest.schema != UPDATE_SCHEMA:
        raise RuntimeError(
            "Unsupported update manifest "
            f"schema: {manifest.schema}"
        )

    if (
        manifest.channel
        != UPDATE_CHANNEL
    ):
        return current_version

    failed_version = (
        read_failed_update_version()
    )

    if (
        failed_version
        == manifest.version
    ):
        log(
            "Skipping previously failed "
            f"update {manifest.version}"
        )

        return current_version

    if (
        manifest.launcher_protocol
        > LAUNCHER_PROTOCOL
    ):
        log(
            "A newer launcher protocol "
            "is required for the latest app."
        )

        return current_version

    if (
        current_version is not None
        and not is_newer(
            manifest.version,
            current_version,
        )
    ):
        return current_version

    UPDATE_CACHE.mkdir(
        parents=True,
        exist_ok=True,
    )

    archive = (
        UPDATE_CACHE
        / (
            "EU5-AI-Companion-App-"
            f"{manifest.version}-"
            "win-x64.zip"
        )
    )

    log(
        "Downloading update "
        f"{manifest.version}"
    )

    download_package(
        manifest.package_url,
        archive,
    )

    verify_package(
        archive,
        manifest.sha256,
    )

    install_package(
        archive,
        APP_DIR,
        manifest.version,
        APP_EXECUTABLE,
    )

    write_current_version(
        manifest.version
    )

    log(
        "Activated update "
        f"{manifest.version}"
    )

    return manifest.version


def launch_version(
    version: str,
) -> None:
    executable = executable_for(
        version
    )

    if not executable.is_file():
        raise FileNotFoundError(
            "Application executable "
            "not found: "
            f"{executable}"
        )

    subprocess.Popen(
        [
            str(executable),
            *sys.argv[1:],
        ],
        cwd=executable.parent,
    )


def main() -> int:
    previous_version = (
        read_current_version()
    )

    if (
        previous_version is None
        or not executable_for(
            previous_version
        ).is_file()
    ):
        previous_version = (
            choose_fallback_version()
        )

        if previous_version:
            write_current_version(
                previous_version
            )

    selected_version = (
        previous_version
    )

    try:
        selected_version = maybe_update(
            previous_version
        )

    except Exception as exc:
        log(
            "Update check failed: "
            f"{type(exc).__name__}: {exc}"
        )

    if selected_version is None:
        show_error(
            APP_NAME,
            "No installed EU5 AI Companion "
            "application version was found, "
            "and no update could be installed.",
        )

        return 1

    try:
        launch_version(
            selected_version
        )

        return 0

    except Exception as exc:
        log(
            "Launch failed for "
            f"{selected_version}: "
            f"{type(exc).__name__}: {exc}"
        )

        if (
            previous_version
            and previous_version
            != selected_version
            and executable_for(
                previous_version
            ).is_file()
        ):
            try:
                mark_failed_update(
                    selected_version
                )

                failed_directory = (
                    executable_for(
                        selected_version
                    )
                    .parent
                )

                if failed_directory.is_dir():
                    shutil.rmtree(
                        failed_directory,
                        ignore_errors=True,
                    )

                write_current_version(
                    previous_version
                )

                launch_version(
                    previous_version
                )

                log(
                    "Rolled back to "
                    f"{previous_version}; "
                    f"marked {selected_version} "
                    "as failed."
                )

                return 0

            except Exception as rollback_exc:
                log(
                    "Rollback launch failed: "
                    + "".join(
                        traceback.format_exception(
                            rollback_exc
                        )
                    )
                )

        show_error(
            APP_NAME,
            "EU5 AI Companion could not "
            "be started. See launcher.log "
            "under LocalAppData for details.",
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
