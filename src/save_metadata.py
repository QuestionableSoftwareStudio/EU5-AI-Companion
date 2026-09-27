from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import subprocess


@dataclass
class SaveMetadata:
    path: Path
    date: str | None
    country_name: str | None
    version: str | None
    playthrough_name: str | None
    save_label: str | None
    ironman: bool
    modified: float
    size: int


def _value(line: str) -> str:
    value = line.split("=", 1)[1].strip()

    if (
        len(value) >= 2
        and value[0] == '"'
        and value[-1] == '"'
    ):
        value = value[1:-1]

    return value


def read_save_metadata(
    rakaly: Path,
    save_file: Path,
    max_bytes: int = 512 * 1024,
) -> SaveMetadata:

    stat = save_file.stat()

    process = subprocess.Popen(
        [
            str(rakaly),
            "melt",
            "-c",
            "--format",
            "eu5",
            "-u",
            "stringify",
            str(save_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    fields = {
        "date": None,
        "player_country_name": None,
        "version": None,
        "playthrough_name": None,
        "save_label": None,
    }

    consumed = 0

    try:
        assert process.stdout is not None

        while consumed < max_bytes:

            raw = process.stdout.readline()

            if not raw:
                break

            consumed += len(raw)

            line = raw.decode(
                "utf-8",
                errors="replace",
            ).strip()

            for key in fields:
                if (
                    fields[key] is None
                    and line.startswith(
                        key + "="
                    )
                ):
                    fields[key] = _value(
                        line
                    )

            if (
                fields["date"]
                and fields[
                    "player_country_name"
                ]
                and fields["version"]
                and (
                    fields["save_label"]
                    or consumed
                    >= 128 * 1024
                )
            ):
                break

    finally:
        process.terminate()

        try:
            process.wait(
                timeout=1
            )
        except subprocess.TimeoutExpired:
            process.kill()


    ironman = (
        fields["save_label"]
        == "Ironman Saved Game"
        or save_file.name.lower().startswith(
            "sp_ironman_"
        )
    )


    return SaveMetadata(
        path=save_file,
        date=fields["date"],
        country_name=fields[
            "player_country_name"
        ],
        version=fields["version"],
        playthrough_name=fields[
            "playthrough_name"
        ],
        save_label=fields[
            "save_label"
        ],
        ironman=ironman,
        modified=stat.st_mtime,
        size=stat.st_size,
    )


def _load_cache(
    cache_path: Path,
) -> dict:

    if not cache_path.exists():
        return {}

    try:
        data = json.loads(
            cache_path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def _save_cache(
    cache_path: Path,
    cache: dict,
):

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path.write_text(
        json.dumps(
            cache,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def list_saves(
    rakaly: Path,
    save_dir: Path,
    cache_path: Path | None = None,
) -> list[SaveMetadata]:

    if cache_path is None:
        cache_path = (
            Path(__file__)
            .resolve()
            .parent
            .parent
            / ".cache"
            / "save_metadata.json"
        )


    cache = _load_cache(
        cache_path
    )

    files = sorted(
        (
            path
            for path
            in save_dir.glob("*.eu5")
            if path.name.lower()
            != "companion_live.eu5"
            and not path.name.lower().endswith(
                "_melted.eu5"
            )
        ),
        key=lambda path:
            path.stat().st_mtime,
        reverse=True,
    )


    result = []
    active_keys = set()


    for save_file in files:

        key = str(
            save_file.resolve()
        )

        active_keys.add(key)

        stat = save_file.stat()

        cached = cache.get(
            key
        )


        if (
            cached
            and cached.get("size")
            == stat.st_size
            and cached.get("modified")
            == stat.st_mtime
        ):

            meta = SaveMetadata(
                path=save_file,
                date=cached.get("date"),
                country_name=cached.get(
                    "country_name"
                ),
                version=cached.get(
                    "version"
                ),
                playthrough_name=cached.get(
                    "playthrough_name"
                ),
                save_label=cached.get(
                    "save_label"
                ),
                ironman=bool(
                    cached.get(
                        "ironman",
                        False,
                    )
                ),
                modified=stat.st_mtime,
                size=stat.st_size,
            )

        else:

            try:
                meta = read_save_metadata(
                    rakaly,
                    save_file,
                )

            except Exception:
                continue


            cached_data = asdict(
                meta
            )

            cached_data.pop(
                "path",
                None,
            )

            cache[key] = cached_data


        result.append(
            meta
        )


    stale = [
        key
        for key in cache
        if key not in active_keys
    ]

    for key in stale:
        cache.pop(
            key,
            None,
        )


    _save_cache(
        cache_path,
        cache,
    )

    return result


if __name__ == "__main__":

    import sys
    import time

    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: save_metadata.py "
            "RAKALY SAVE_DIR"
        )


    rakaly = Path(
        sys.argv[1]
    )

    save_dir = Path(
        sys.argv[2]
    )


    started = time.perf_counter()


    saves = list_saves(
        rakaly,
        save_dir,
    )


    for save in saves:

        kind = (
            "IRONMAN"
            if save.ironman
            else "NORMAL"
        )

        print(
            f"{kind:7} | "
            f"{save.country_name or '?':20} | "
            f"{save.date or '?':12} | "
            f"{save.version or '?':8} | "
            f"{save.path.name}"
        )


    print()

    print(
        f"{len(saves)} saves scanned in "
        f"{time.perf_counter() - started:.3f}s"
    )
