from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile


USER_AGENT = "EU5-AI-Companion-Updater/1"


@dataclass(frozen=True)
class UpdateManifest:
    schema: int
    channel: str
    version: str
    launcher_protocol: int
    package_url: str
    sha256: str


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.strip().lstrip("v").split(".")

    if len(parts) != 3:
        raise ValueError(
            f"Invalid version: {value!r}"
        )

    try:
        return tuple(
            int(part)
            for part in parts
        )

    except ValueError as exc:
        raise ValueError(
            f"Invalid version: {value!r}"
        ) from exc


def is_newer(
    candidate: str,
    current: str,
) -> bool:
    return (
        version_tuple(candidate)
        > version_tuple(current)
    )


def fetch_manifest(
    url: str,
    timeout: float = 3.0,
) -> UpdateManifest:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        data = json.loads(
            response.read().decode("utf-8-sig")
        )

    required = (
        "schema",
        "channel",
        "version",
        "launcher_protocol",
        "package_url",
        "sha256",
    )

    missing = [
        key
        for key in required
        if key not in data
    ]

    if missing:
        raise ValueError(
            "Update manifest missing: "
            + ", ".join(missing)
        )

    return UpdateManifest(
        schema=int(data["schema"]),
        channel=str(data["channel"]),
        version=str(data["version"]),
        launcher_protocol=int(
            data["launcher_protocol"]
        ),
        package_url=str(
            data["package_url"]
        ),
        sha256=str(
            data["sha256"]
        ).strip().lower(),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            block = file.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def download_package(
    url: str,
    destination: Path,
    timeout: float = 30.0,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    partial = destination.with_suffix(
        destination.suffix + ".part"
    )

    if partial.exists():
        partial.unlink()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            with partial.open("wb") as file:
                shutil.copyfileobj(
                    response,
                    file,
                    length=1024 * 1024,
                )

        partial.replace(destination)

    finally:
        if partial.exists():
            partial.unlink()


def verify_package(
    path: Path,
    expected_sha256: str,
) -> None:
    actual = sha256_file(path)
    expected = (
        expected_sha256
        .strip()
        .lower()
    )

    if actual != expected:
        raise RuntimeError(
            "Update SHA-256 mismatch. "
            f"Expected {expected}, "
            f"received {actual}."
        )


def _safe_extract(
    archive: Path,
    destination: Path,
) -> None:
    destination = destination.resolve()

    with zipfile.ZipFile(
        archive,
        "r",
    ) as zip_file:
        for member in zip_file.infolist():
            target = (
                destination
                / member.filename
            ).resolve()

            try:
                target.relative_to(
                    destination
                )

            except ValueError as exc:
                raise RuntimeError(
                    "Unsafe path in update ZIP: "
                    f"{member.filename}"
                ) from exc

        zip_file.extractall(destination)


def install_package(
    archive: Path,
    app_root: Path,
    version: str,
    expected_executable: str,
) -> Path:
    version_tuple(version)

    app_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_directory = (
        app_root
        / version
    )

    final_executable = (
        final_directory
        / expected_executable
    )

    if final_executable.is_file():
        return final_executable

    if final_directory.exists():
        raise RuntimeError(
            "Version directory already exists "
            "but is incomplete: "
            f"{final_directory}"
        )

    staging = (
        app_root
        / f".{version}.installing"
    )

    if staging.exists():
        shutil.rmtree(staging)

    staging.mkdir(
        parents=True,
        exist_ok=False,
    )

    try:
        _safe_extract(
            archive,
            staging,
        )

        staged_executable = (
            staging
            / expected_executable
        )

        if not staged_executable.is_file():
            raise RuntimeError(
                "Downloaded update does not "
                "contain expected executable: "
                f"{expected_executable}"
            )

        staging.replace(
            final_directory
        )

    except Exception:
        if staging.exists():
            shutil.rmtree(
                staging,
                ignore_errors=True,
            )

        raise

    if not final_executable.is_file():
        raise RuntimeError(
            "Update installation did not "
            "produce the expected executable."
        )

    return final_executable
