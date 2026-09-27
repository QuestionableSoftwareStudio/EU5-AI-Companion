from pathlib import Path
import sys
import ijson

path = Path(sys.argv[1])

sections = {
    "metadata",
    "countries",
    "market_manager",
    "loan_manager",
    "trade_manager",
    "international_organization_manager",
    "advance_manager",
    "terra_incognita",
}

root_scalars = {
    "start_of_day",
    "current_age",
    "speed",
    "played_country",
    "first_start",
    "previous_played",
}

MAX_KEYS = 30

found_scalars = {}
section_keys = {name: [] for name in sections}
section_types = {}

with path.open("rb") as f:
    for prefix, event, value in ijson.parse(f):

        if prefix in root_scalars and event in {
            "string", "number", "boolean", "null"
        }:
            found_scalars[prefix] = value

        if prefix in sections and event in {
            "start_map", "start_array",
            "string", "number", "boolean", "null"
        }:
            section_types.setdefault(prefix, event)

        if event == "map_key" and prefix in sections:
            if len(section_keys[prefix]) < MAX_KEYS:
                section_keys[prefix].append(value)

print("ROOT VALUES")
print("=" * 60)

for name in sorted(root_scalars):
    print(f"{name}: {found_scalars.get(name, '<not scalar>')}")

for section in sections:
    print()
    print(section.upper())
    print("=" * 60)
    print(f"type: {section_types.get(section, '<not found>')}")

    if section_keys[section]:
        print("first immediate keys:")
        for key in section_keys[section]:
            print(f"  {key}")
    else:
        print("no immediate map keys")
