from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import shutil

from game_paths import find_eu5_save_directory
from runtime_paths import APP_ROOT


MOD_ID = "eu5_ai_companion"

SOURCE_MOD = (
    APP_ROOT
    / "resources"
    / "eu5_ai_companion_mod"
)


@dataclass
class ModInstallResult:
    status: str
    source: Path
    target: Path | None
    changed_files: int = 0


def _file_hash(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(
            1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _files_equal(
    source: Path,
    target: Path,
) -> bool:

    if not target.exists():
        return False

    if source.stat().st_size != target.stat().st_size:
        return False

    return (
        _file_hash(source)
        == _file_hash(target)
    )


def ensure_companion_mod() -> ModInstallResult:

    if not SOURCE_MOD.exists():
        raise FileNotFoundError(
            "Bundled EU5 AI Companion mod "
            f"was not found: {SOURCE_MOD}"
        )

    save_dir = (
        find_eu5_save_directory()
    )

    if save_dir is None:
        return ModInstallResult(
            status="eu5_user_dir_not_found",
            source=SOURCE_MOD,
            target=None,
        )

    eu5_user_dir = (
        save_dir.parent
    )

    target = (
        eu5_user_dir
        / "mod"
        / MOD_ID
    )

    target.mkdir(
        parents=True,
        exist_ok=True,
    )

    changed = 0

    source_files = {
        path.relative_to(
            SOURCE_MOD
        )
        for path in SOURCE_MOD.rglob("*")
        if path.is_file()
    }

    # Copy missing/changed files.
    for relative in sorted(
        source_files,
        key=str,
    ):

        source_file = (
            SOURCE_MOD
            / relative
        )

        target_file = (
            target
            / relative
        )

        if _files_equal(
            source_file,
            target_file,
        ):
            continue

        target_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_file,
            target_file,
        )

        changed += 1

    # Remove obsolete files from our own mod directory.
    for target_file in sorted(
        (
            path
            for path in target.rglob("*")
            if path.is_file()
        ),
        key=lambda p: len(p.parts),
        reverse=True,
    ):

        relative = (
            target_file.relative_to(
                target
            )
        )

        if relative not in source_files:
            target_file.unlink()
            changed += 1

    # Remove now-empty obsolete directories.
    for directory in sorted(
        (
            path
            for path in target.rglob("*")
            if path.is_dir()
        ),
        key=lambda p: len(p.parts),
        reverse=True,
    ):

        try:
            directory.rmdir()
        except OSError:
            pass

    return ModInstallResult(
        status=(
            "updated"
            if changed
            else "current"
        ),
        source=SOURCE_MOD,
        target=target,
        changed_files=changed,
    )


if __name__ == "__main__":

    result = (
        ensure_companion_mod()
    )

    print(
        f"Companion mod: {result.status}"
    )

    print(
        f"Source: {result.source}"
    )

    print(
        f"Target: {result.target}"
    )

    print(
        f"Changed files: "
        f"{result.changed_files}"
    )
