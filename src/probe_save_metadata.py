from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: probe_save_metadata.py RAKALY SAVE_DIR"
    )


rakaly = Path(
    sys.argv[1]
).resolve()

save_dir = Path(
    sys.argv[2]
).resolve()


if not rakaly.exists():
    raise SystemExit(
        f"Rakaly not found: {rakaly}"
    )

if not save_dir.exists():
    raise SystemExit(
        f"Save directory not found: {save_dir}"
    )


save_files = sorted(
    (
        path
        for path in save_dir.glob("*.eu5")
        if path.name.lower()
        != "companion_live.eu5"
    ),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)


print("=" * 72)
print("EU5 SAVE METADATA PROBE")
print("=" * 72)

print(
    f"Saves found: {len(save_files)}"
)

print()


for save_file in save_files[:10]:

    print("-" * 72)

    print(
        save_file.name
    )


    result = subprocess.run(
        [
            str(rakaly),
            "json",
            str(save_file),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


    if result.returncode != 0:

        print(
            "Rakaly failed:",
            result.stderr.strip(),
        )

        continue


    try:
        root = json.loads(
            result.stdout
        )

    except Exception as exc:

        print(
            "JSON failed:",
            exc,
        )

        continue


    metadata = root.get(
        "metadata",
        {}
    )


    print(
        "metadata keys:"
    )

    for key in sorted(
        metadata.keys()
    ):

        value = metadata[
            key
        ]


        lowered = (
            key.lower()
        )


        if any(
            word in lowered
            for word in (
                "iron",
                "achievement",
                "multiplayer",
                "player",
                "country",
                "flag",
                "date",
                "version",
            )
        ):

            print(
                f"  {key}: "
                f"{value!r}"
            )


    print()
    print(
        "Possible Ironman-related values "
        "anywhere near the top level:"
    )


    found = False


    def walk(
        value,
        path="",
        depth=0,
    ):

        nonlocal_found = False

        if depth > 4:
            return False


        if isinstance(
            value,
            dict,
        ):

            for key, item in (
                value.items()
            ):

                full = (
                    f"{path}.{key}"
                    if path
                    else key
                )


                if (
                    "iron" in str(
                        key
                    ).lower()
                ):

                    print(
                        f"  {full}: "
                        f"{item!r}"
                    )

                    nonlocal_found = True


                if walk(
                    item,
                    full,
                    depth + 1,
                ):
                    nonlocal_found = True


        elif isinstance(
            value,
            list,
        ):

            # Don't recurse huge arrays during this probe.
            for index, item in enumerate(
                value[:20]
            ):

                if walk(
                    item,
                    f"{path}[{index}]",
                    depth + 1,
                ):
                    nonlocal_found = True


        return nonlocal_found


    found = walk(
        root
    )


    if not found:

        print(
            "  none found"
        )


print()
print("=" * 72)
print("DONE")
print("=" * 72)
