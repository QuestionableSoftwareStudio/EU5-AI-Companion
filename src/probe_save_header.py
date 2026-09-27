from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import time


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: probe_save_header.py RAKALY SAVE_FILE"
    )


rakaly = Path(sys.argv[1]).resolve()
save_file = Path(sys.argv[2]).resolve()


MAX_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 64 * 1024


started = time.perf_counter()


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
    stderr=subprocess.PIPE,
)


buffer = bytearray()


try:

    while len(buffer) < MAX_BYTES:

        chunk = process.stdout.read(
            CHUNK_SIZE
        )

        if not chunk:
            break

        buffer.extend(chunk)


finally:

    process.terminate()

    try:
        process.wait(
            timeout=2
        )
    except subprocess.TimeoutExpired:
        process.kill()


elapsed = (
    time.perf_counter()
    - started
)


text = bytes(buffer).decode(
    "utf-8",
    errors="replace",
)


print("=" * 72)
print("EU5 PARTIAL SAVE HEADER PROBE")
print("=" * 72)

print(
    f"Save:       {save_file.name}"
)

print(
    f"Read:       {len(buffer) / 1024:.1f} KB"
)

print(
    f"Time:       {elapsed:.3f}s"
)


print()
print("=" * 72)
print("INTERESTING LINES")
print("=" * 72)


keywords = (
    "iron",
    "achievement",
    "flag",
    "version",
    "player",
    "country",
    "date",
    "start_of_day",
    "played_country",
)


interesting = []


for line in text.splitlines():

    lowered = line.lower()

    if any(
        keyword in lowered
        for keyword in keywords
    ):

        interesting.append(
            line.strip()
        )


for line in interesting[:100]:
    print(line)


if not interesting:
    print(
        "No matching lines in the first "
        f"{len(buffer) / 1024:.0f} KB."
    )


print()
print("=" * 72)
print("FIRST TOP-LEVEL-LOOKING KEYS")
print("=" * 72)


top_level_pattern = re.compile(
    r"^([A-Za-z0-9_]+)\s*="
)


seen = set()
count = 0


for line in text.splitlines():

    match = top_level_pattern.match(
        line
    )

    if not match:
        continue

    key = match.group(1)

    if key in seen:
        continue

    seen.add(key)

    print(key)

    count += 1

    if count >= 40:
        break


print()
print("=" * 72)
print("DONE")
print("=" * 72)
