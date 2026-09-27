from pathlib import Path
import codecs
import io
import sys

import ijson


def open_json(path: Path):
    raw = path.open("rb")
    header = raw.read(4)
    raw.seek(0)

    if header.startswith(codecs.BOM_UTF16_LE) or header.startswith(codecs.BOM_UTF16_BE):
        print("Encoding: UTF-16")
        return io.TextIOWrapper(raw, encoding="utf-16")

    if header.startswith(codecs.BOM_UTF8):
        print("Encoding: UTF-8 BOM")
        return io.TextIOWrapper(raw, encoding="utf-8-sig")

    print("Encoding: UTF-8")
    return io.TextIOWrapper(raw, encoding="utf-8")


path = Path(sys.argv[1])

print(f"File: {path}")
print(f"Size: {path.stat().st_size / 1024 / 1024:.2f} MB")
print()
print("Top-level EU5 save keys:")
print("-" * 40)

with open_json(path) as f:
    for prefix, event, value in ijson.parse(f):
        if prefix == "" and event == "map_key":
            print(value)
