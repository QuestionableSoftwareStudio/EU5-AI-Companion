from __future__ import annotations

from runtime_paths import (
    CAMPAIGN_DB,
    TEMP_EU5_DIR,
    initialize_runtime,
)
from eu5_pause_guard import PauseGuardError, pause_for_snapshot

import json
import os
import re
import ijson
from pathlib import Path
import subprocess
import sqlite3
import sys
import time


if len(sys.argv) < 5:
    raise SystemExit(
        r"""
Usage:

  ask_eu5.py EU5_PID RAKALY PROJECT_ROOT QUESTION

Example:

  ask_eu5.py 12345 rakaly.exe PROJECT_ROOT "Why the fuck is fine cloth so expensive?"
""".strip()
    )


eu5_pid = int(
    sys.argv[1]
)

rakaly = Path(
    sys.argv[2]
).resolve()

project = Path(
    sys.argv[3]
).resolve()

question = " ".join(
    sys.argv[4:]
).strip()


if not question:
    raise SystemExit(
        "Question cannot be empty"
    )


initialize_runtime()

db_path = CAMPAIGN_DB

python = sys.executable

provider = os.environ.get(
    "AI_PROVIDER",
    "openai",
).strip().lower()


if provider == "groq":

    api_key = os.environ.get(
        "GROQ_API_KEY"
    )

    model = os.environ.get(
        "AI_MODEL",
        "openai/gpt-oss-120b",
    )

    base_url = (
        "https://api.groq.com/openai/v1"
    )


elif provider == "openai":

    api_key = os.environ.get(
        "OPENAI_API_KEY"
    )

    model = os.environ.get(
        "AI_MODEL",
        os.environ.get(
            "OPENAI_MODEL",
            "gpt-5.6-luna",
        ),
    )

    base_url = None


else:

    raise RuntimeError(
        f"Unknown AI provider: "
        f"{provider}"
    )



# ============================================================
# Model instructions
# ============================================================

INSTRUCTIONS = """
You are an AI co-gamer and advisor for Europa Universalis V.

The human player always makes all gameplay decisions and actions.
You never control the game.

IMPORTANT DATA RULES:

- Current-campaign factual claims must come from the supplied local tools.
- The local database was captured from an exact-current-date EU5 save.
- Do not invent values that are not present in tool results.
- Do not assume a cheaper foreign market is reachable or profitable.
- Do not assume import/export flags mean more than the tool output states.
- If route cost, merchant capacity, connectivity, or another required value
  is missing, explicitly say that it is not yet represented.
- Never infer hidden AI intentions or hidden game state.
- A complete current player-country save object may be exposed by a local tool.
  Treat unfamiliar raw field names conservatively: use their values as evidence,
  but do not invent undocumented gameplay semantics for them.
- For current patches, recent news, release notes, documentation, or
  other time-sensitive external information, use the available hosted
  web-search/browser-search tool.
- For current campaign facts, prefer the local EU5 campaign tools.
- Do not replace current campaign data with web information.
- If external search fails or provides insufficient evidence, say so rather
  than guessing.
- Use player-facing names in normal prose instead of internal IDs wherever
  possible.
- Be concise but useful.
- Explain causes using the actual numbers when they materially help.
- You may suggest options for the player to consider, but the player makes
  the decision.

Economy and markets have specialized tools, but you are NOT limited to
economy. For military, government, diplomacy, technology, population,
estates, culture/religion, laws, modifiers, and other player-country systems,
use get_player_country_state. Combine all relevant requested topics into one
focused search query when possible. If a raw field is unclear, explain the
uncertainty instead of inventing a meaning.
""".strip()


# ============================================================
# Tool definitions exposed to OpenAI
# ============================================================

LOCAL_TOOLS = [
    {
        "type": "function",
        "name": "get_player_overview",
        "description": (
            "Get the current player country, exact game date, "
            "basic economy, capital, and the markets containing "
            "the player's territory. Use this when the question "
            "needs general current-country context or when you "
            "need to determine the player's market ID."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "get_player_country_state",
        "description": (
            "Search the complete exact-current human player-country save "
            "object without sending the entire object to the model. Use "
            "this for military, government, diplomacy, technology, "
            "population, estates, culture/religion, laws, modifiers, "
            "court, subjects, and other non-economic systems. Supply "
            "space-separated keywords or likely EU5 field names. The tool "
            "returns compact matching paths and values and may be called "
            "again with narrower keywords. Raw EU5 field names can be "
            "unclear, so do not invent undocumented semantics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Space-separated search terms, for example "
                        "'army regiment manpower levy military' or "
                        "'government law estate legitimacy'."
                    ),
                },
            },
            "required": [
                "query",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "get_market_brief",
        "description": (
            "Get a compact player-visible analysis of one market, "
            "including current shortages, surpluses, prices, "
            "supply, demand, and cheaper visible price references."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "market_id": {
                    "type": "integer",
                    "description": (
                        "Runtime market ID from the current campaign."
                    ),
                },
            },
            "required": [
                "market_id",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "get_good_brief",
        "description": (
            "Get current player-visible information about a trade good "
            "across visible markets. Includes the player's own market "
            "price/supply/demand plus low and high visible prices. "
            "Use this for questions about why a good is expensive, "
            "cheap, scarce, abundant, or how its market compares."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "good": {
                    "type": "string",
                    "description": (
                        "Player-facing or internal good name, "
                        "for example Fine Cloth, Iron, Fish."
                    ),
                },
            },
            "required": [
                "good",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ============================================================
# Provider-specific tool set
# ============================================================

TOOLS = list(
    LOCAL_TOOLS
)


if provider == "groq":

    # Groq GPT-OSS 20B/120B hosted browser search.
    TOOLS.append(
        {
            "type": "browser_search",
        }
    )


elif provider == "openai":

    # OpenAI hosted live web search.
    TOOLS.append(
        {
            "type": "web_search",
        }
    )


# ============================================================
# Fresh exact-current-state capture
# ============================================================

print("=" * 70)
print("EU5 AI COMPANION")
print("=" * 70)

print()
print("Routing request...")


overall_started = (
    time.perf_counter()
)


capture_completed = False
capture_elapsed = 0.0

full_world_ready = False
core_state = None
advisor = None


decoded_snapshot = (
    TEMP_EU5_DIR
    / "decoded_current.json"
)

core_snapshot_file = (
    TEMP_EU5_DIR
    / "core_state.json"
)

player_country_file = (
    TEMP_EU5_DIR
    / "player_country.json"
)


def ensure_campaign_state():
    """
    Acquire the exact-current snapshot and only the cheap
    player/core state.

    Full locations/countries/markets are imported lazily only
    if an AI tool actually needs them.
    """

    global capture_completed
    global capture_elapsed
    global core_state


    if capture_completed:
        return


    if eu5_pid <= 0:
        raise RuntimeError(
            "EU5 is not currently running. "
            "Start EU5 for questions that require "
            "current campaign data."
        )


    # --------------------------------------------------------
    # Positive pause acknowledgement BEFORE requesting save.
    # Never weaken this guard.
    # --------------------------------------------------------

    try:
        pause_for_snapshot(
            eu5_pid,
            project,
        )

    except PauseGuardError as exc:

        message = str(
            exc
        )

        if "did not confirm" in message:
            raise RuntimeError(
                "NO_LIVE_CAMPAIGN: "
                "No EU5 campaign is currently loaded. "
                "Load or start a campaign, then ask again."
            ) from exc

        raise RuntimeError(
            message
        ) from exc


    print()
    print(
        "Fetching current game state...",
        flush=True,
    )


    capture_started = (
        time.perf_counter()
    )


    capture_env = (
        os.environ.copy()
    )

    capture_env[
        "EU5_COMPANION_ALREADY_PAUSED"
    ] = "1"


    capture = subprocess.run(
        [
            sys.executable,

            str(
                project
                / "src"
                / "capture_core_state.py"
            ),

            str(
                eu5_pid
            ),

            str(
                rakaly
            ),

            str(
                project
            ),
        ],

        cwd=project,
        env=capture_env,
    )


    if capture.returncode == 20:
        raise RuntimeError(
            "NO_LIVE_CAMPAIGN: "
            "No EU5 campaign is currently loaded. "
            "Load or start a campaign, then ask again."
        )


    if capture.returncode != 0:
        raise RuntimeError(
            "Fresh EU5 core capture failed "
            f"with exit code "
            f"{capture.returncode}"
        )


    if not core_snapshot_file.exists():
        raise RuntimeError(
            "Fast capture completed but "
            "core_state.json is missing."
        )


    core_state = json.loads(
        core_snapshot_file.read_text(
            encoding="utf-8"
        )
    )


    capture_elapsed = (
        time.perf_counter()
        - capture_started
    )

    capture_completed = True


def ensure_full_world_state():
    """
    Import the expensive visible-world slice only when a tool
    actually needs markets, goods, locations, etc.

    This uses decoded_current.json from the SAME exact save
    captured by ensure_campaign_state(); EU5 is not saved again.
    """

    global full_world_ready
    global advisor
    global capture_elapsed


    ensure_campaign_state()


    if full_world_ready:
        return


    if not decoded_snapshot.exists():

        source_save = Path(
            str(
                core_state.get(
                    "_source_save",
                    "",
                )
            )
        )

        if not source_save.is_file():
            raise RuntimeError(
                "The exact source save for this "
                "question is no longer available."
            )

        print()
        print(
            "Decoding detailed snapshot...",
            flush=True,
        )

        decode_started = (
            time.perf_counter()
        )

        decode = subprocess.run(
            [
                sys.executable,
                str(
                    project
                    / "src"
                    / "decode_save.py"
                ),
                str(
                    rakaly
                ),
                str(
                    source_save
                ),
                str(
                    decoded_snapshot
                ),
            ],
            cwd=project,
        )

        if decode.returncode != 0:
            raise RuntimeError(
                "Detailed Rakaly decode failed "
                f"with exit code "
                f"{decode.returncode}"
            )

        capture_elapsed += (
            time.perf_counter()
            - decode_started
        )


    print()
    print(
        "Loading detailed visible-world data...",
        flush=True,
    )


    started = (
        time.perf_counter()
    )


    result = subprocess.run(
        [
            sys.executable,

            str(
                project
                / "src"
                / "stream_visible_world_to_db.py"
            ),

            str(
                decoded_snapshot
            ),

            str(
                db_path
            ),
        ],

        cwd=project,
    )


    elapsed = (
        time.perf_counter()
        - started
    )

    capture_elapsed += (
        elapsed
    )


    if result.returncode != 0:
        raise RuntimeError(
            "Detailed visible-world import failed "
            f"with exit code "
            f"{result.returncode}"
        )


    # Heavy advisor/database helper is needed only now.
    from advisor_context import (
        AdvisorContext,
    )


    advisor = AdvisorContext(
        str(
            db_path
        )
    )

    full_world_ready = True


# ============================================================
# Sanitized local functions
# ============================================================

def get_core_overview():
    ensure_campaign_state()

    return {
        "as_of": dict(
            core_state.get(
                "as_of",
                {},
            )
        ),

        "player": dict(
            core_state.get(
                "player",
                {},
            )
        ),

        "detail_level": "core",

        "detail_note": (
            "This exact snapshot contains current "
            "player/country economy data. Detailed "
            "market/location/world data is loaded "
            "only when a tool requests it."
        ),
    }


def _compact_country_value(
    value,
    depth: int = 0,
):
    """
    Keep tool output comfortably below hosted-provider token limits.
    """

    if value is None or isinstance(
        value,
        (
            bool,
            int,
            float,
        ),
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        if len(value) <= 240:
            return value

        return (
            value[:237]
            + "..."
        )

    if isinstance(
        value,
        list,
    ):
        items = [
            _compact_country_value(
                item,
                depth + 1,
            )
            for item in value[:8]
        ]

        if len(value) > 8:
            items.append(
                f"... {len(value) - 8} more items"
            )

        return items

    if isinstance(
        value,
        dict,
    ):
        keys = list(
            value.keys()
        )

        if depth >= 2:
            return {
                "_keys": [
                    str(key)
                    for key in keys[:16]
                ],
                "_key_count": len(keys),
            }

        result = {}

        for key in keys[:10]:
            result[
                str(key)
            ] = _compact_country_value(
                value[key],
                depth + 1,
            )

        if len(keys) > 10:
            result[
                "_truncated_keys"
            ] = (
                len(keys)
                - 10
            )

        return result

    return str(
        value
    )[:240]


def get_player_country_state(
    query: str,
):
    """
    Search the complete exact-current player-country object locally
    and return only compact matching paths/values.

    The full save object never gets inserted into the AI request.
    """

    ensure_campaign_state()

    player_id = (
        core_state
        .get("player", {})
        .get("country_id")
    )

    if player_id is None:
        raise RuntimeError(
            "Current player country ID is unavailable."
        )

    query_terms = [
        term
        for term in re.findall(
            r"[a-z0-9_]+",
            str(
                query
            ).lower(),
        )
        if len(term) >= 2
    ]

    if not query_terms:
        raise ValueError(
            "Provide at least one player-country search term."
        )

    if not player_country_file.is_file():
        raise RuntimeError(
            "The exact current player-country snapshot is missing."
        )

    player_country = json.loads(
        player_country_file.read_text(
            encoding="utf-8"
        )
    )

    matches = []
    max_matches = 18

    def visit(
        value,
        path: str,
    ):
        if len(
            matches
        ) >= max_matches:
            return

        if isinstance(
            value,
            dict,
        ):
            for key, child in value.items():

                child_path = (
                    f"{path}.{key}"
                    if path
                    else str(
                        key
                    )
                )

                searchable = (
                    child_path
                    .lower()
                    .replace(
                        "-",
                        "_",
                    )
                )

                if any(
                    term in searchable
                    for term in query_terms
                ):
                    matches.append(
                        {
                            "path": child_path,
                            "value": (
                                _compact_country_value(
                                    child
                                )
                            ),
                        }
                    )

                    if len(
                        matches
                    ) >= max_matches:
                        return

                visit(
                    child,
                    child_path,
                )

                if len(
                    matches
                ) >= max_matches:
                    return

        elif isinstance(
            value,
            list,
        ):
            # Only descend a bounded prefix. Country arrays can be
            # enormous and matching their index paths adds little value.
            for index, child in enumerate(
                value[:24]
            ):
                visit(
                    child,
                    f"{path}[{index}]",
                )

                if len(
                    matches
                ) >= max_matches:
                    return

    visit(
        player_country,
        "",
    )

    return {
        "as_of": dict(
            core_state.get(
                "as_of",
                {},
            )
        ),
        "player_tag": (
            core_state
            .get("player", {})
            .get("tag")
        ),
        "country_id": player_id,
        "query": query,
        "top_level_fields": [
            str(
                key
            )
            for key in list(
                player_country.keys()
            )[:80]
        ],
        "matches": matches,
        "match_limit": max_matches,
        "truncated": (
            len(
                matches
            )
            >= max_matches
        ),
        "data_note": (
            "Matches come from the exact-current human player-country "
            "save object. Results are deliberately compact to stay "
            "within provider token limits. Search again with narrower "
            "keywords when more detail is needed."
        ),
    }


def get_player_overview():
    """
    Full overview tool.

    Unlike the automatically injected core snapshot, this tool
    also returns the player's runtime market IDs.
    """

    ensure_full_world_state()

    overview = (
        get_core_overview()
    )

    player_id = (
        overview[
            "player"
        ].get(
            "country_id"
        )
    )


    markets = []

    with sqlite3.connect(
        db_path
    ) as conn:

        conn.row_factory = (
            sqlite3.Row
        )

        rows = conn.execute(
            """
            SELECT DISTINCT
                m.market_id,
                m.center_location_id,
                m.population,
                m.capacity,
                m.food,
                m.max_food,
                m.price
            FROM current_locations AS l
            JOIN current_markets AS m
                ON m.market_id = l.market_id
            WHERE
                l.owner_id = ?
                AND l.market_id IS NOT NULL
            ORDER BY
                m.market_id
            """,
            (
                player_id,
            ),
        ).fetchall()


        markets = [
            dict(
                row
            )
            for row in rows
        ]


    overview[
        "markets"
    ] = markets

    overview[
        "detail_level"
    ] = "full-player-overview"

    return overview


def execute_tool(
    name: str,
    arguments: dict,
):

    # Exact core snapshot is always acquired first.
    ensure_campaign_state()


    if name == "get_player_overview":
        return get_player_overview()


    if name == "get_player_country_state":
        return get_player_country_state(
            str(
                arguments[
                    "query"
                ]
            )
        )


    if name == "get_market_brief":

        ensure_full_world_state()

        return advisor.market_brief(
            int(
                arguments[
                    "market_id"
                ]
            )
        )


    if name == "get_good_brief":

        ensure_full_world_state()

        return advisor.good_brief(
            str(
                arguments[
                    "good"
                ]
            )
        )


    return {
        "error": (
            f"Unknown local tool: {name}"
        )
    }


# ============================================================
# Decide whether this question requires the current campaign.
#
# Freshness is owned by the Companion, not by the LLM.
# ============================================================

def requires_live_campaign(
    text: str,
) -> bool:

    q = " ".join(
        text.lower().split()
    )

    phrases = (
        "my ",
        "our ",
        "current ",
        "right now",
        "at the moment",
        "why am i",
        "why are we",
        "why is my",
        "why is our",
        "how do i",
        "how can i",
        "what should i",
        "should i",
        "can i afford",
        "do i have",
        "am i ",
    )

    return any(
        phrase in q
        for phrase in phrases
    )


preloaded_player_overview = None


if requires_live_campaign(
    question
):

    try:

        ensure_campaign_state()

    except RuntimeError as exc:

        error_text = str(
            exc
        )

        if error_text.startswith(
            "NO_LIVE_CAMPAIGN:"
        ):

            message = (
                error_text
                .split(":", 1)[1]
                .strip()
            )

            print()
            print(
                f"You: {question}"
            )
            print()
            print(
                message
            )
            print()
            print(
                "=" * 70
            )
            print(
                "Campaign state:          not used"
            )
            print(
                "AI time:                 0.00s"
            )

            raise SystemExit(0)

        if (
            "EU5 is not currently running"
            in error_text
        ):

            print()
            print(
                f"You: {question}"
            )
            print()
            print(
                "Europa Universalis V is not "
                "currently running. Start EU5 "
                "and load a campaign, then ask again."
            )
            print()
            print(
                "=" * 70
            )
            print(
                "Campaign state:          not used"
            )
            print(
                "AI time:                 0.00s"
            )

            raise SystemExit(0)

        raise


    preloaded_player_overview = (
        get_core_overview()
    )


# ============================================================
# OpenAI tool-call loop
# ============================================================

# Import the model/API stack late so live campaign questions
# reach the EU5 pause/capture path as quickly as possible.
from openai import (
    BadRequestError,
    OpenAI,
)

from api_usage import ApiUsageTracker

if not api_key:

    required_variable = (
        "GROQ_API_KEY"
        if provider == "groq"
        else "OPENAI_API_KEY"
    )

    raise RuntimeError(
        f"{required_variable} is not set"
    )


client_kwargs = {
    "api_key": api_key,
}


if base_url:

    client_kwargs[
        "base_url"
    ] = base_url


client = OpenAI(
    **client_kwargs
)


usage_tracker = ApiUsageTracker()


input_items = [
    {
        "role": "user",
        "content": question,
    }
]


if preloaded_player_overview is not None:

    input_items.append(
        {
            "role": "user",
            "content": (
                "CURRENT EXACT EU5 CAMPAIGN DATA "
                "(captured immediately before this "
                "answer):\n"
                + json.dumps(
                    preloaded_player_overview,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n\nBase your answer on this "
                "current campaign state. "
                "Do not substitute generic assumptions. "
                "Use the supplied tools when more detail is needed. "
                "For non-economic player-country questions, use "
                "get_player_country_state with focused search terms "
                "rather than guessing or requesting the entire save."
            ),
        }
    )


api_started = (
    time.perf_counter()
)


ALLOWED_TOOL_NAMES = (
    "get_player_overview",
    "get_player_country_state",
    "get_market_brief",
    "get_good_brief",
)


def is_invalid_tool_error(
    exc: BadRequestError,
) -> bool:

    if provider != "groq":
        return False

    error_text = str(
        exc
    ).lower()

    return (
        (
            "attempted to call tool"
            in error_text
            and
            "not in request.tools"
            in error_text
        )
        or
        "tool call validation failed"
        in error_text
    )


def create_model_response(
    tool_choice: str,
):
    """
    Call the provider once normally.

    If Groq/GPT-OSS invents a tool that was not supplied,
    retry exactly once with an explicit allowed-tool reminder.
    """

    try:

        return client.responses.create(
            model=model,
            instructions=INSTRUCTIONS,
            input=input_items,
            tools=TOOLS,
            tool_choice=tool_choice,
        )

    except BadRequestError as exc:

        if not is_invalid_tool_error(
            exc
        ):
            raise

        print(
            "Provider attempted to use an "
            "unavailable tool; retrying once "
            "with strict tool names...",
            flush=True,
        )

        allowed = ", ".join(
            ALLOWED_TOOL_NAMES
        )

        retry_instructions = (
            INSTRUCTIONS
            + "\n\n"
            + "IMPORTANT TOOL CONSTRAINT: "
            + "You may call ONLY the tools "
            + "explicitly supplied in this request. "
            + "The allowed local tool names are: "
            + allowed
            + ". "
            + "Do not invent, infer, alias, or call "
            + "tools such as find, search, browse, "
            + "lookup, grep, or any other undeclared "
            + "tool. If none of the supplied tools "
            + "can answer the request, answer using "
            + "the information already available."
        )

        try:

            return client.responses.create(
                model=model,
                instructions=retry_instructions,
                input=input_items,
                tools=TOOLS,
                tool_choice=tool_choice,
            )

        except BadRequestError as retry_exc:

            if is_invalid_tool_error(
                retry_exc
            ):
                raise RuntimeError(
                    "The AI provider attempted to use "
                    "an unavailable tool twice. "
                    "Please try the question again."
                ) from retry_exc

            raise


def question_needs_live_state(
    text: str,
) -> bool:
    """
    Conservative MVP heuristic.

    First-person/current-state gameplay questions should use
    the player's actual campaign rather than generic advice.
    """

    q = " ".join(
        text.lower().split()
    )

    live_phrases = (
        "my ",
        "our ",
        "current ",
        "right now",
        "at the moment",
        "why am i",
        "why are we",
        "why is my",
        "why is our",
        "how do i",
        "how can i",
        "what should i",
        "should i",
        "can i afford",
        "do i have",
        "am i ",
    )

    return any(
        phrase in q
        for phrase in live_phrases
    )


MAX_TOOL_ROUNDS = 6


try:

    response = create_model_response(
        "auto"
    )


except BadRequestError as exc:

    error_text = str(
        exc
    )


    if (
        provider == "groq"
        and (
            "tool_use_failed"
            in error_text
            or
            "model did not call a tool"
            in error_text
        )
    ):

        if question_needs_live_state(
            question
        ):

            print(
                "Provider skipped a required "
                "live-campaign tool; retrying "
                "once with explicit instructions...",
                flush=True,
            )

            strict_instructions = (
                INSTRUCTIONS
                + "\n\n"
                + "This question is about the user's "
                + "CURRENT loaded EU5 campaign. "
                + "You MUST call one of the supplied "
                + "campaign-data tools before answering. "
                + "Do not answer from generic EU5 knowledge "
                + "and do not guess campaign state."
            )

            try:
                response = client.responses.create(
                    model=model,
                    instructions=strict_instructions,
                    input=input_items,
                    tools=TOOLS,
                    tool_choice="auto",
                )

            except BadRequestError as retry_exc:
                raise RuntimeError(
                    "The AI provider could not use the "
                    "required live-campaign tools. "
                    "Please try the question again."
                ) from retry_exc

        else:

            print(
                "Provider declined forced tool use; "
                "retrying with automatic tool choice..."
            )

            response = create_model_response(
                "auto"
            )


    else:

        raise


usage_tracker.add_response(
    response
)


live_tool_retry_done = False


for round_number in range(
    MAX_TOOL_ROUNDS
):

    function_calls = [
        item
        for item in response.output
        if item.type == "function_call"
    ]


    if not function_calls:

        if (
            question_needs_live_state(
                question
            )
            and not capture_completed
        ):

            if live_tool_retry_done:
                raise RuntimeError(
                    "The AI provider returned an answer "
                    "without reading the current campaign "
                    "after two attempts."
                )

            live_tool_retry_done = True

            print(
                "Provider returned text without "
                "reading campaign state; retrying "
                "once with a mandatory live tool...",
                flush=True,
            )

            strict_live_instructions = (
                INSTRUCTIONS
                + "\n\n"
                + "MANDATORY CURRENT-CAMPAIGN QUERY: "
                + "Do not answer this question from "
                + "general Europa Universalis V knowledge. "
                + "You MUST call one of the supplied "
                + "campaign-data tools before answering. "
                + "Use only supplied tool names. "
                + "If no campaign is loaded, the tool "
                + "will report that condition."
            )

            response = (
                client.responses.create(
                    model=model,
                    instructions=(
                        strict_live_instructions
                    ),
                    input=input_items,
                    tools=TOOLS,
                    tool_choice="auto",
                )
            )

            usage_tracker.add_response(
                response
            )

            continue

        break


    # Preserve the model's response items, including reasoning/tool calls.
    input_items.extend(
        response.output
    )


    for call in function_calls:

        try:
            arguments = json.loads(
                call.arguments
            )

            print(
                f"Reading: "
                f"{call.name}"
                f"({arguments})"
            )


            tool_result = execute_tool(
                call.name,
                arguments,
            )


        except Exception as exc:

            tool_result = {
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
            }


        input_items.append(
            {
                "type": (
                    "function_call_output"
                ),
                "call_id": call.call_id,
                "output": json.dumps(
                    tool_result,
                    ensure_ascii=False,
                    separators=(
                        ",",
                        ":",
                    ),
                ),
            }
        )


    response = create_model_response(
        (
            "none"
            if provider == "groq"
            else "auto"
        )
    )

    usage_tracker.add_response(
        response
    )


else:
    raise RuntimeError(
        "Model exceeded the maximum "
        "number of local tool rounds"
    )


api_elapsed = (
    time.perf_counter()
    - api_started
)


# ============================================================
# Answer
# ============================================================

answer = (
    response.output_text
    or ""
).strip()


print()
print("=" * 70)


if (
    capture_completed
    and core_state is not None
):

    live_player = (
        core_state.get(
            "player",
            {}
        )
    )

    live_as_of = (
        core_state.get(
            "as_of",
            {}
        )
    )

    live_tag = (
        live_player.get(
            "tag"
        )
        or "UNKNOWN"
    )

    live_date = (
        live_as_of.get(
            "game_date"
        )
        or "UNKNOWN"
    )

    print(
        f"LIVE | "
        f"{live_tag} | "
        f"{live_date}"
    )


else:

    print(
        "EXTERNAL / GENERAL"
    )


print("=" * 70)
print()


print(
    f"You: {question}"
)

print()


print(
    answer
    if answer
    else "[No text response returned]"
)


overall_elapsed = (
    time.perf_counter()
    - overall_started
)


print()
print("=" * 70)

capture_text = (
    f"{capture_elapsed:.2f}s"
    if capture_completed
    else "not used"
)


print(
    f"Campaign state:          "
    f"{'used' if capture_completed else 'not used'}"
)

print(
    f"Fresh-state acquisition: "
    f"{capture_text}"
)

print(
    f"OpenAI reasoning:        "
    f"{api_elapsed:.2f}s"
)

print(
    f"Total:                   "
    f"{overall_elapsed:.2f}s"
)

print(
    f"Provider:                "
    f"{provider}"
)

print(
    f"Model:                   "
    f"{model}"
)

print()
print("API USAGE")
print("-" * 70)

print(
    f"API requests:            "
    f"{usage_tracker.requests}"
)

print(
    f"Input tokens:            "
    f"{usage_tracker.input_tokens:,}"
)

print(
    f"  ordinary input:        "
    f"{usage_tracker.ordinary_input_tokens:,}"
)

print(
    f"  cached input:          "
    f"{usage_tracker.cached_input_tokens:,}"
)

print(
    f"  cache writes:          "
    f"{usage_tracker.cache_write_tokens:,}"
)

print(
    f"Output tokens:           "
    f"{usage_tracker.output_tokens:,}"
)

print(
    f"  reasoning tokens:      "
    f"{usage_tracker.reasoning_tokens:,}"
)

print(
    f"Total tokens:            "
    f"{usage_tracker.total_tokens:,}"
)

print(
    f"Estimated API cost:      "
    f"{usage_tracker.cost_text()}"
)

if usage_tracker.unpriced_models:

    print(
        "Unpriced model(s):       "
        + ", ".join(
            sorted(
                usage_tracker.unpriced_models
            )
        )
    )

print("=" * 70)
