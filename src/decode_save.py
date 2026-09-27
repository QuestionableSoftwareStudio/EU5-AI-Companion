from pathlib import Path
import subprocess
import sys
import time

rakaly = Path(sys.argv[1])
save = Path(sys.argv[2])
out = Path(sys.argv[3])

out.parent.mkdir(parents=True, exist_ok=True)

print(f"Decoding: {save.name}")
started = time.perf_counter()

with out.open("wb") as f:
    result = subprocess.run(
        [str(rakaly), "json", str(save)],
        stdout=f,
        stderr=subprocess.PIPE
    )

elapsed = time.perf_counter() - started

if result.returncode != 0:
    print(result.stderr.decode(errors="replace"))
    raise SystemExit(result.returncode)

print(f"Finished in {elapsed:.2f}s")
print(f"Output: {out}")
print(f"Size: {out.stat().st_size / 1024 / 1024:.2f} MB")
