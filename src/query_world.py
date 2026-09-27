from pprint import pprint
import sys

from world_state import WorldState


if len(sys.argv) < 3:
    raise SystemExit(
        """
Usage:
  query_world.py DB state
  query_world.py DB player
  query_world.py DB country TAG_OR_ID
  query_world.py DB markets TAG_OR_ID
  query_world.py DB market MARKET_ID
  query_world.py DB location LOCATION_ID
  query_world.py DB shortages MARKET_ID
  query_world.py DB surpluses MARKET_ID
  query_world.py DB good GOOD
  query_world.py DB producers GOOD
  query_world.py DB history MARKET_ID GOOD
""".strip()
    )


db = WorldState(
    sys.argv[1]
)

command = sys.argv[2]


if command == "state":

    pprint(
        db.get_campaign_state()
    )


elif command == "player":

    pprint(
        db.get_player_country()
    )


elif command == "country":

    if len(sys.argv) < 4:
        raise SystemExit(
            "country TAG_OR_ID"
        )

    pprint(
        db.get_country(
            sys.argv[3]
        )
    )


elif command == "markets":

    if len(sys.argv) < 4:
        raise SystemExit(
            "markets TAG_OR_ID"
        )

    pprint(
        db.get_country_markets(
            sys.argv[3]
        )
    )


elif command == "market":

    if len(sys.argv) < 4:
        raise SystemExit(
            "market MARKET_ID"
        )

    pprint(
        db.get_market(
            int(sys.argv[3])
        )
    )


elif command == "location":

    if len(sys.argv) < 4:
        raise SystemExit(
            "location LOCATION_ID"
        )

    pprint(
        db.get_location(
            int(sys.argv[3])
        )
    )


elif command == "shortages":

    if len(sys.argv) < 4:
        raise SystemExit(
            "shortages MARKET_ID"
        )

    pprint(
        db.get_market_shortages(
            int(sys.argv[3])
        )
    )


elif command == "surpluses":

    if len(sys.argv) < 4:
        raise SystemExit(
            "surpluses MARKET_ID"
        )

    pprint(
        db.get_market_surpluses(
            int(sys.argv[3])
        )
    )


elif command == "good":

    if len(sys.argv) < 4:
        raise SystemExit(
            "good GOOD"
        )

    good = " ".join(
        sys.argv[3:]
    )

    pprint(
        db.get_good_worldwide(
            good
        )
    )


elif command == "producers":

    if len(sys.argv) < 4:
        raise SystemExit(
            "producers GOOD"
        )

    good = " ".join(
        sys.argv[3:]
    )

    pprint(
        db.get_raw_material_producers(
            good,
            limit=30,
        )
    )


elif command == "history":

    if len(sys.argv) < 5:
        raise SystemExit(
            "history MARKET_ID GOOD"
        )

    good = " ".join(
        sys.argv[4:]
    )

    pprint(
        db.get_good_history(
            int(sys.argv[3]),
            good,
        )
    )


else:

    raise SystemExit(
        f"Unknown command: {command}"
    )
