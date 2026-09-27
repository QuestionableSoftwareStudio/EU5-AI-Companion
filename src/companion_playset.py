from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import tempfile

from companion_mod import ensure_companion_mod
from game_paths import find_eu5_save_directory


@dataclass
class PlaysetResult:
    status: str
    playsets_file: Path | None
    playset_name: str | None = None
    changed: bool = False


def _normalized_mod_path(
    path: str,
) -> str:

    return (
        path
        .replace("\\", "/")
        .rstrip("/")
        .lower()
    )


def ensure_companion_playset_enabled() -> PlaysetResult:

    mod_result = (
        ensure_companion_mod()
    )

    if mod_result.target is None:
        return PlaysetResult(
            status="eu5_user_dir_not_found",
            playsets_file=None,
        )

    save_dir = (
        find_eu5_save_directory()
    )

    if save_dir is None:
        return PlaysetResult(
            status="eu5_user_dir_not_found",
            playsets_file=None,
        )

    eu5_user_dir = (
        save_dir.parent
    )

    playsets_file = (
        eu5_user_dir
        / "playsets.json"
    )

    if not playsets_file.exists():
        return PlaysetResult(
            status="playsets_missing",
            playsets_file=playsets_file,
        )

    try:

        data = json.loads(
            playsets_file.read_text(
                encoding="utf-8-sig",
            )
        )

    except Exception as exc:

        raise RuntimeError(
            "Could not read EU5 playsets.json"
        ) from exc


    playsets = (
        data.get("playsets")
        or []
    )

    active = next(
        (
            playset
            for playset in playsets
            if playset.get(
                "isActive"
            ) is True
        ),
        None,
    )

    if active is None:

        return PlaysetResult(
            status="no_active_playset",
            playsets_file=playsets_file,
        )


    mods = active.setdefault(
        "orderedListMods",
        [],
    )

    target_path = (
        mod_result.target
        .resolve()
        .as_posix()
        + "/"
    )

    normalized_target = (
        _normalized_mod_path(
            target_path
        )
    )

    existing = None

    for mod in mods:

        path = mod.get(
            "path"
        )

        if not isinstance(
            path,
            str,
        ):
            continue

        if (
            _normalized_mod_path(path)
            == normalized_target
        ):
            existing = mod
            break


    changed = False

    if existing is None:

        mods.append(
            {
                "path": target_path,
                "isEnabled": True,
            }
        )

        changed = True

    else:

        if (
            existing.get("path")
            != target_path
        ):

            existing[
                "path"
            ] = target_path

            changed = True


        if (
            existing.get(
                "isEnabled"
            )
            is not True
        ):

            existing[
                "isEnabled"
            ] = True

            changed = True


    if changed:

        # Keep a simple recovery copy of the
        # user's launcher state before editing.
        backup = (
            playsets_file
            .with_suffix(
                ".json.companion-backup"
            )
        )

        if not backup.exists():
            backup.write_bytes(
                playsets_file.read_bytes()
            )


        encoded = (
            json.dumps(
                data,
                indent=4,
                ensure_ascii=False,
            )
            + "\n"
        )


        fd, temp_name = (
            tempfile.mkstemp(
                prefix="playsets_",
                suffix=".json",
                dir=str(
                    playsets_file.parent
                ),
            )
        )

        try:

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as file:

                file.write(
                    encoded
                )


            os.replace(
                temp_name,
                playsets_file,
            )

        finally:

            temp_path = Path(
                temp_name
            )

            if temp_path.exists():
                temp_path.unlink()


    return PlaysetResult(
        status=(
            "updated"
            if changed
            else "current"
        ),
        playsets_file=playsets_file,
        playset_name=active.get(
            "name"
        ),
        changed=changed,
    )


if __name__ == "__main__":

    result = (
        ensure_companion_playset_enabled()
    )

    print(
        f"Playset: {result.status}"
    )

    print(
        f"File: {result.playsets_file}"
    )

    print(
        f"Active playset: "
        f"{result.playset_name}"
    )

    print(
        f"Changed: {result.changed}"
    )
