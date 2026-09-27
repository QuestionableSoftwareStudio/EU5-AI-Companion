from pathlib import Path
import subprocess
import sys
import time

rakaly = Path(sys.argv[1])
save = Path(sys.argv[2])
out = Path(sys.argv[3])

out.parent.mkdir(parents=True, exist_ok=True)

print(f"Decoding: {save.name}", flush=True)
started = time.perf_counter()

DECODE_TIMEOUT = 300.0

try:
    with out.open("wb") as f:
        result = subprocess.run(
            [str(rakaly), "json", str(save)],
            stdout=f,
            stderr=subprocess.PIPE,
            timeout=DECODE_TIMEOUT,
        )

except subprocess.TimeoutExpired as exc:
    try:
        out.unlink(missing_ok=True)
    except OSError:
        pass

    print(
        f"Rakaly decode timed out after {DECODE_TIMEOUT:.0f}s.",
        flush=True,
    )
    print(
        "The partial decoded file was removed. "
        "Please retry the request.",
        flush=True,
    )
    raise SystemExit(124) from exc

elapsed = time.perf_counter() - started

if result.returncode != 0:
    try:
        out.unlink(missing_ok=True)
    except OSError:
        pass

    print(result.stderr.decode(errors="replace"))
    raise SystemExit(result.returncode)

print(f"Finished in {elapsed:.2f}s")
print(f"Output: {out}")
print(f"Size: {out.stat().st_size / 1024 / 1024:.2f} MB")
