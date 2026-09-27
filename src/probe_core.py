from pathlib import Path
import sys
import ijson

path = Path(sys.argv[1])

TARGETS = [
    "metadata",
    "played_country",
    "countries.tags",
    "countries.database",
    "market_manager.produced_goods",
    "market_manager.database",
]

LIMIT = 35
captured = {target: [] for target in TARGETS}

def display_value(event, value):
    if event in {"string", "number", "boolean", "null", "map_key"}:
        text = repr(value)
        if len(text) > 140:
            text = text[:137] + "..."
        return text
    return ""

with path.open("rb") as f:
    for prefix, event, value in ijson.parse(f):
        for target in TARGETS:
            if len(captured[target]) >= LIMIT:
                continue

            if prefix == target or prefix.startswith(target + "."):
                relative = prefix[len(target):].lstrip(".")
                if not relative:
                    relative = "<root>"

                captured[target].append(
                    (relative, event, display_value(event, value))
                )

for target in TARGETS:
    print()
    print("=" * 80)
    print(target)
    print("=" * 80)

    for relative, event, value in captured[target]:
        if value:
            print(f"{relative:<40} {event:<12} {value}")
        else:
            print(f"{relative:<40} {event}")
