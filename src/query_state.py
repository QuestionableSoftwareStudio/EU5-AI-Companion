from pprint import pprint
import sys

from campaign_state import CampaignState


if len(sys.argv) < 3:
    raise SystemExit(
        "Usage: query_state.py SNAPSHOT COMMAND [ARGS...]"
    )

snapshot = sys.argv[1]
command = sys.argv[2]

state = CampaignState(snapshot)


if command == "summary":
    pprint(state.summary())

elif command == "economy":
    pprint(state.get_player_economy())

elif command == "markets":
    for market_id, market in state.get_player_markets().items():
        print(
            market_id,
            "center=",
            market.get("center"),
            "population=",
            market.get("population"),
            "capacity=",
            market.get("capacity"),
        )

elif command == "good":
    if len(sys.argv) < 5:
        raise SystemExit(
            "Usage: query_state.py SNAPSHOT good MARKET_ID GOOD"
        )

    market_id = sys.argv[3]
    good = sys.argv[4]

    result = state.get_good_summary(market_id, good)

    if result is None:
        raise SystemExit("Good or market not found.")

    pprint(result)

elif command == "location":
    if len(sys.argv) < 4:
        raise SystemExit(
            "Usage: query_state.py SNAPSHOT location LOCATION_ID"
        )

    pprint(state.get_location(sys.argv[3]))

else:
    raise SystemExit(f"Unknown command: {command}")
