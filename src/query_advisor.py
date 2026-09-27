from __future__ import annotations

import json
import sys

from advisor_context import AdvisorContext


if len(sys.argv) < 3:
    raise SystemExit(
        """
Usage:
  query_advisor.py DB market MARKET_ID
  query_advisor.py DB good GOOD
""".strip()
    )


db_path = sys.argv[1]
command = sys.argv[2]

advisor = AdvisorContext(
    db_path
)


if command == "market":

    if len(sys.argv) < 4:
        raise SystemExit(
            "market MARKET_ID"
        )

    result = advisor.market_brief(
        int(sys.argv[3])
    )


elif command == "good":

    if len(sys.argv) < 4:
        raise SystemExit(
            "good GOOD"
        )

    good = " ".join(
        sys.argv[3:]
    )

    result = advisor.good_brief(
        good
    )


else:
    raise SystemExit(
        f"Unknown command: {command}"
    )


print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )
)
