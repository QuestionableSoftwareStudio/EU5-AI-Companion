from __future__ import annotations

from runtime_paths import GAME_PATHS_CONFIG, initialize_runtime

import ctypes
import json
import os
import re
import sys

from ctypes import wintypes
from pathlib import Path


EU5_APP_ID = "3450310"
EU5_EXE_RELATIVE = Path("binaries") / "eu5.exe"

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

initialize_runtime()

PATH_CONFIG = GAME_PATHS_CONFIG


# =========================================================
# Persistent manual overrides
# =========================================================

def _load_config() -> dict:

    if not PATH_CONFIG.exists():
        return {}

    try:
        data = json.loads(
            PATH_CONFIG.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def _save_config(
    data: dict,
) -> None:

    PATH_CONFIG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    PATH_CONFIG.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def save_manual_eu5_executable(
    exe: Path,
) -> None:

    exe = exe.resolve()

    if not exe.is_file():
        raise ValueError(
            f"EU5 executable does not exist: {exe}"
        )

    if exe.name.lower() != "eu5.exe":
        raise ValueError(
            "Selected file is not eu5.exe"
        )

    config = _load_config()

    config["eu5_executable"] = str(
        exe
    )

    _save_config(
        config
    )


def clear_manual_eu5_executable() -> None:

    config = _load_config()

    config.pop(
        "eu5_executable",
        None,
    )

    _save_config(
        config
    )


def get_manual_eu5_executable(
) -> Path | None:

    value = _load_config().get(
        "eu5_executable"
    )

    if not value:
        return None

    path = Path(
        value
    )

    if (
        path.is_file()
        and path.name.lower()
        == "eu5.exe"
    ):
        return path

    return None


# =========================================================
# Windows known Documents folder
# =========================================================

def _windows_documents_folder(
) -> Path | None:

    if sys.platform != "win32":
        return None

    try:

        class GUID(
            ctypes.Structure
        ):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                (
                    "Data4",
                    ctypes.c_ubyte * 8,
                ),
            ]


        # FOLDERID_Documents
        folder_id = GUID(
            0xFDD39AD0,
            0x238F,
            0x46AF,
            (
                ctypes.c_ubyte * 8
            )(
                0xAD,
                0xB4,
                0x6C,
                0x85,
                0x48,
                0x03,
                0x69,
                0xC7,
            ),
        )


        path_ptr = (
            ctypes.c_wchar_p()
        )


        shell32 = (
            ctypes.windll.shell32
        )

        ole32 = (
            ctypes.windll.ole32
        )


        result = (
            shell32.SHGetKnownFolderPath(
                ctypes.byref(
                    folder_id
                ),
                0,
                None,
                ctypes.byref(
                    path_ptr
                ),
            )
        )


        if result != 0:
            return None


        try:
            value = path_ptr.value

            if value:
                return Path(
                    value
                )

        finally:
            ole32.CoTaskMemFree(
                path_ptr
            )


    except Exception:
        pass

    return None


def find_eu5_save_directory(
) -> Path | None:

    candidates = []


    known_documents = (
        _windows_documents_folder()
    )

    if known_documents:
        candidates.append(
            known_documents
        )


    home_documents = (
        Path.home()
        / "Documents"
    )

    if home_documents not in candidates:
        candidates.append(
            home_documents
        )


    onedrive = os.environ.get(
        "OneDrive"
    )

    if onedrive:

        candidate = (
            Path(onedrive)
            / "Documents"
        )

        if candidate not in candidates:
            candidates.append(
                candidate
            )


    for documents in candidates:

        save_dir = (
            documents
            / "Paradox Interactive"
            / "Europa Universalis V"
            / "save games"
        )

        if save_dir.is_dir():
            return save_dir


    return None


# =========================================================
# Steam discovery
# =========================================================

def _registry_steam_roots(
) -> list[Path]:

    roots = []

    if sys.platform != "win32":
        return roots


    try:
        import winreg

        locations = [
            (
                winreg.HKEY_CURRENT_USER,
                r"Software\Valve\Steam",
                "SteamPath",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\Valve\Steam",
                "InstallPath",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                (
                    r"Software\WOW6432Node"
                    r"\Valve\Steam"
                ),
                "InstallPath",
            ),
        ]


        for (
            hive,
            key_name,
            value_name,
        ) in locations:

            try:

                with winreg.OpenKey(
                    hive,
                    key_name,
                ) as key:

                    value, _ = (
                        winreg.QueryValueEx(
                            key,
                            value_name,
                        )
                    )

                    path = Path(
                        value
                    )

                    if path not in roots:
                        roots.append(
                            path
                        )

            except OSError:
                pass


    except Exception:
        pass


    return roots


def find_steam_roots(
) -> list[Path]:

    roots = (
        _registry_steam_roots()
    )


    for fallback in (
        Path(
            r"C:\Program Files (x86)\Steam"
        ),
        Path(
            r"C:\Program Files\Steam"
        ),
    ):

        if (
            fallback.is_dir()
            and fallback not in roots
        ):
            roots.append(
                fallback
            )


    return roots


def _parse_libraryfolders(
    steam_root: Path,
) -> list[Path]:

    result = [
        steam_root
    ]


    file = (
        steam_root
        / "steamapps"
        / "libraryfolders.vdf"
    )


    if not file.exists():
        return result


    try:

        raw = file.read_text(
            encoding="utf-8",
            errors="ignore",
        )


        for match in re.finditer(
            r'"path"\s*"([^"]+)"',
            raw,
        ):

            value = (
                match.group(1)
                .replace(
                    "\\\\",
                    "\\",
                )
            )

            path = Path(
                value
            )

            if path not in result:
                result.append(
                    path
                )


    except Exception:
        pass


    return result


def find_steam_libraries(
) -> list[Path]:

    libraries = []


    for steam_root in find_steam_roots():

        for library in (
            _parse_libraryfolders(
                steam_root
            )
        ):

            if library not in libraries:
                libraries.append(
                    library
                )


    return libraries


# =========================================================
# EU5 install discovery
# =========================================================

def _read_manifest_installdir(
    manifest: Path,
) -> str | None:

    try:

        raw = manifest.read_text(
            encoding="utf-8",
            errors="ignore",
        )


        match = re.search(
            r'"installdir"\s*"([^"]+)"',
            raw,
            re.IGNORECASE,
        )


        if match:
            return match.group(1)


    except Exception:
        pass


    return None


def find_eu5_executable(
) -> Path | None:

    # Manual override gets first priority.

    manual = (
        get_manual_eu5_executable()
    )

    if manual:
        return manual


    # Steam manifests are authoritative for
    # Steam installations.

    for library in find_steam_libraries():

        steamapps = (
            library
            / "steamapps"
        )


        manifest = (
            steamapps
            / f"appmanifest_{EU5_APP_ID}.acf"
        )


        if not manifest.exists():
            continue


        install_dir = (
            _read_manifest_installdir(
                manifest
            )
        )


        if not install_dir:
            continue


        candidate = (
            steamapps
            / "common"
            / install_dir
            / EU5_EXE_RELATIVE
        )


        if candidate.is_file():
            return candidate


    # Last-resort legacy folder-name check.

    for library in find_steam_libraries():

        candidate = (
            library
            / "steamapps"
            / "common"
            / "Europa Universalis V"
            / EU5_EXE_RELATIVE
        )

        if candidate.is_file():
            return candidate


    return None


# =========================================================
# Diagnostics
# =========================================================

if __name__ == "__main__":

    print(
        "Steam roots:"
    )

    for item in find_steam_roots():
        print(
            " ",
            item,
        )


    print()
    print(
        "Steam libraries:"
    )

    for item in find_steam_libraries():
        print(
            " ",
            item,
        )


    print()
    print(
        "EU5 executable:"
    )

    print(
        " ",
        find_eu5_executable(),
    )


    print()
    print(
        "EU5 save directory:"
    )

    print(
        " ",
        find_eu5_save_directory(),
    )
