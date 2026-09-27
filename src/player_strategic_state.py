from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json
import subprocess

import ijson
from ijson.common import ObjectBuilder


FORMAL_RELATION_HINTS = (
    "alliance",
    "ally",
    "scripted",
    "dependency",
    "subject",
    "vassal",
    "union",
    "marriage",
    "guarantee",
    "access",
    "embargo",
    "rival",
    "enemy",
    "tributary",
    "march",
    "fiefdom",
)


def _relation_references_player(
    value: Any,
    player_id: int,
    player_tag: str,
) -> bool:
    """
    Match only explicit country endpoints inside diplomacy objects.
    This avoids treating arbitrary IDs in foreign relations as if they
    referred to the human player.
    """

    endpoint_keys = {
        "first",
        "second",
        "country",
        "actor",
        "target_country",
        "overlord",
        "subject",
        "giver",
        "receiver",
    }

    if isinstance(
        value,
        dict,
    ):
        for key, child in value.items():
            lower = str(
                key
            ).lower()

            if lower in endpoint_keys:

                if (
                    isinstance(
                        child,
                        int,
                    )
                    and child == player_id
                ):
                    return True

                if (
                    isinstance(
                        child,
                        str,
                    )
                    and (
                        child == str(
                            player_id
                        )
                        or child.upper()
                        == player_tag.upper()
                    )
                ):
                    return True

            if isinstance(
                child,
                (
                    dict,
                    list,
                ),
            ) and _relation_references_player(
                child,
                player_id,
                player_tag,
            ):
                return True

    elif isinstance(
        value,
        list,
    ):
        return any(
            _relation_references_player(
                child,
                player_id,
                player_tag,
            )
            for child in value
            if isinstance(
                child,
                (
                    dict,
                    list,
                ),
            )
        )

    return False


def _compact(
    value: Any,
    depth: int = 0,
):
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
        return (
            value
            if len(value) <= 180
            else value[:177] + "..."
        )

    if isinstance(
        value,
        list,
    ):
        result = [
            _compact(
                item,
                depth + 1,
            )
            for item in value[:12]
        ]

        if len(value) > 12:
            result.append(
                f"... {len(value) - 12} more"
            )

        return result

    if isinstance(
        value,
        dict,
    ):
        if depth >= 3:
            keys = list(
                value.keys()
            )

            return {
                "_keys": [
                    str(
                        key
                    )
                    for key in keys[:20]
                ],
                "_key_count": len(
                    keys
                ),
            }

        result = {}

        for key, child in list(
            value.items()
        )[:18]:
            result[
                str(
                    key
                )
            ] = _compact(
                child,
                depth + 1,
            )

        if len(value) > 18:
            result[
                "_truncated_keys"
            ] = (
                len(value)
                - 18
            )

        return result

    return str(
        value
    )[:180]


def _iter_relation_candidates(
    value: Any,
    path: str,
):
    """
    diplomacy_manager layouts vary by relation type and game patch.
    Walk captured manager branches and yield small dict-shaped
    candidates rather than assuming one fixed layout.
    """

    if isinstance(
        value,
        dict,
    ):
        yield (
            path,
            value,
        )

        for key, child in value.items():
            if isinstance(
                child,
                (
                    dict,
                    list,
                ),
            ):
                child_path = (
                    f"{path}.{key}"
                    if path
                    else str(
                        key
                    )
                )

                yield from (
                    _iter_relation_candidates(
                        child,
                        child_path,
                    )
                )

    elif isinstance(
        value,
        list,
    ):
        for index, child in enumerate(
            value
        ):
            if isinstance(
                child,
                (
                    dict,
                    list,
                ),
            ):
                yield from (
                    _iter_relation_candidates(
                        child,
                        f"{path}[{index}]",
                    )
                )


def _relation_country_ids(
    value: dict,
):
    """
    Extract likely country endpoints from diplomacy relation objects.
    EU5 setup/runtime relations commonly use first/second; additional
    names cover subject and actor/target variants without treating every
    integer in the object as a country ID.
    """

    endpoint_keys = {
        "first",
        "second",
        "country",
        "actor",
        "target_country",
        "overlord",
        "subject",
        "giver",
        "receiver",
    }

    result = set()

    def walk(
        obj,
    ):
        if isinstance(
            obj,
            dict,
        ):
            for key, child in obj.items():
                lower = str(
                    key
                ).lower()

                if lower in endpoint_keys:

                    if isinstance(
                        child,
                        int,
                    ):
                        result.add(
                            child
                        )

                    elif (
                        isinstance(
                            child,
                            str,
                        )
                        and child.isdigit()
                    ):
                        result.add(
                            int(
                                child
                            )
                        )

                if isinstance(
                    child,
                    (
                        dict,
                        list,
                    ),
                ):
                    walk(
                        child
                    )

        elif isinstance(
            obj,
            list,
        ):
            for child in obj:
                if isinstance(
                    child,
                    (
                        dict,
                        list,
                    ),
                ):
                    walk(
                        child
                    )

    walk(
        value
    )

    return result


def _relation_priority(
    path: str,
    value: dict,
):
    searchable = (
        path.lower()
        + " "
        + " ".join(
            str(
                item
            ).lower()
            for item in value.values()
            if isinstance(
                item,
                (
                    str,
                    int,
                ),
            )
        )
    )

    if any(
        hint in searchable
        for hint in FORMAL_RELATION_HINTS
    ):
        return 0

    if (
        "opinion"
        in searchable
        or "trust"
        in searchable
        or "antagon"
        in searchable
    ):
        return 2

    return 1


def _summarize_military(
    player_country: dict,
    subunits: dict[str, dict],
    units: dict[str, dict],
    characters: dict[str, dict],
):
    currency = (
        player_country.get(
            "currency_data"
        )
        or {}
    )

    type_counts = Counter()
    type_strength = Counter()

    for subunit in subunits.values():
        if not isinstance(
            subunit,
            dict,
        ):
            continue

        unit_type = str(
            subunit.get(
                "type",
                "unknown",
            )
        )

        type_counts[
            unit_type
        ] += 1

        raw_strength = (
            subunit.get(
                "strength"
            )
        )

        if isinstance(
            raw_strength,
            (
                int,
                float,
            ),
        ):
            type_strength[
                unit_type
            ] += float(
                raw_strength
            )


    groups = []

    for unit_id, unit in units.items():
        if not isinstance(
            unit,
            dict,
        ):
            continue

        leader_id = unit.get(
            "leader"
        )

        leader = (
            characters.get(
                str(
                    leader_id
                )
            )
            if leader_id is not None
            else None
        )

        groups.append(
            {
                "unit_id": unit_id,
                "name": unit.get(
                    "name"
                ),
                "is_army": unit.get(
                    "is_army"
                ),
                "location": unit.get(
                    "location"
                ),
                "leader_id": leader_id,
                "leader": (
                    _compact(
                        leader
                    )
                    if isinstance(
                        leader,
                        dict,
                    )
                    else None
                ),
                "frontage": unit.get(
                    "frontage"
                ),
                "food": unit.get(
                    "food"
                ),
                "formation": (
                    unit.get(
                        "formation"
                    )
                    or unit.get(
                        "formation_preference"
                    )
                ),
            }
        )


    return {
        "manpower_raw_thousands": (
            currency.get(
                "manpower"
            )
        ),
        "max_manpower_raw_thousands": (
            player_country.get(
                "max_manpower"
            )
        ),
        "monthly_manpower_raw_thousands": (
            player_country.get(
                "monthly_manpower"
            )
        ),
        "manpower_losses_this_month_raw_thousands": (
            player_country.get(
                "this_months_manpower_losses"
            )
        ),
        "sailors_raw_thousands": (
            currency.get(
                "sailors"
            )
        ),
        "max_sailors_raw_thousands": (
            player_country.get(
                "max_sailors"
            )
        ),
        "army_tradition": (
            currency.get(
                "army_tradition"
            )
        ),
        "navy_tradition": (
            currency.get(
                "navy_tradition"
            )
        ),
        "expected_army_size": (
            player_country.get(
                "expected_army_size"
            )
        ),
        "expected_navy_size": (
            player_country.get(
                "expected_navy_size"
            )
        ),
        "owned_subunit_count": len(
            subunits
        ),
        "unit_group_count": len(
            units
        ),
        "composition": [
            {
                "type": unit_type,
                "count": count,
                "summed_strength": round(
                    type_strength.get(
                        unit_type,
                        0.0,
                    ),
                    5,
                ),
            }
            for unit_type, count in (
                type_counts
                .most_common()
            )
        ],
        "groups": groups[:24],
        "note": (
            "Manpower and sailor save values are stored in thousands. "
            "Subunit strength is a fraction/strength value; exact troop "
            "headcount per regiment requires the game's unit-type "
            "max_strength data."
        ),
    }


def _summarize_war(
    war_id: str,
    war: dict,
    tags: dict[str, str],
):
    goal_type = None
    goal_data = None

    for key in (
        "take_province",
        "superiority",
        "independence",
        "dependency",
        "destroy_army",
        "opinion_improvement",
        "revolt",
        "scripted_oneway",
        "potential_for_diplomacy",
    ):
        value = war.get(
            key
        )

        if isinstance(
            value,
            dict,
        ):
            goal_type = key
            goal_data = value
            break


    participants = []

    for participant in (
        war.get(
            "all",
            []
        )
        or []
    ):
        if not isinstance(
            participant,
            dict,
        ):
            continue

        country_id = participant.get(
            "country"
        )

        history = (
            participant.get(
                "history"
            )
            or {}
        )

        request = (
            history.get(
                "request"
            )
            if isinstance(
                history,
                dict,
            )
            else {}
        ) or {}

        joined = (
            history.get(
                "joined"
            )
            if isinstance(
                history,
                dict,
            )
            else {}
        ) or {}

        participants.append(
            {
                "country_id": country_id,
                "tag": tags.get(
                    str(
                        country_id
                    )
                ),
                "side": request.get(
                    "side"
                ),
                "reason": request.get(
                    "reason"
                ),
                "join_type": request.get(
                    "join_type"
                ),
                "called_ally": request.get(
                    "called_ally"
                ),
                "status": participant.get(
                    "status"
                ),
                "joined_date": (
                    joined.get(
                        "date"
                    )
                    if isinstance(
                        joined,
                        dict,
                    )
                    else None
                ),
                "score": (
                    _compact(
                        joined.get(
                            "score"
                        )
                    )
                    if isinstance(
                        joined,
                        dict,
                    )
                    else None
                ),
                "losses": (
                    _compact(
                        joined.get(
                            "losses"
                        )
                    )
                    if isinstance(
                        joined,
                        dict,
                    )
                    else None
                ),
            }
        )


    return {
        "war_id": war_id,
        "war_name": _compact(
            war.get(
                "war_name"
            )
        ),
        "start_date": war.get(
            "start_date"
        ),
        "end_date": war.get(
            "end_date"
        ),
        "civil_war": bool(
            war.get(
                "has_civil_war"
            )
        ),
        "revolt": bool(
            war.get(
                "revolt"
            )
        ),
        "original_attacker": (
            war.get(
                "original_attacker"
            )
        ),
        "original_target": (
            war.get(
                "original_attacker_target"
            )
        ),
        "goal_type": goal_type,
        "goal": _compact(
            goal_data
        ),
        "attacker_score": war.get(
            "attacker_score"
        ),
        "defender_score": war.get(
            "defender_score"
        ),
        "war_direction_quarter": (
            war.get(
                "war_direction_quarter"
            )
        ),
        "war_direction_year": (
            war.get(
                "war_direction_year"
            )
        ),
        "war_goal_held": war.get(
            "war_goal_held"
        ),
        "participants": participants,
    }


def read_player_strategic_state(
    rakaly: Path,
    save: Path,
    player_id: int,
    player_tag: str,
    player_country: dict,
    include_military: bool = True,
    include_diplomacy: bool = True,
):
    """
    Stream only the managers needed for the human player's
    military/diplomatic state. No full decoded JSON is written.
    """

    owned_subunit_ids = {
        str(
            item
        )
        for item in (
            player_country.get(
                "owned_subunits"
            )
            or []
        )
    }

    unit_ids = {
        str(
            item
        )
        for item in (
            player_country.get(
                "units"
            )
            or []
        )
    }

    subunits: dict[
        str,
        dict,
    ] = {}

    units: dict[
        str,
        dict,
    ] = {}

    characters: dict[
        str,
        dict,
    ] = {}

    leader_ids: set[
        str
    ] = set()

    tags: dict[
        str,
        str,
    ] = {}

    player_wars = []

    relations = []

    process = subprocess.Popen(
        [
            str(
                rakaly
            ),
            "json",
            str(
                save
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if process.stdout is None:
        process.kill()
        raise RuntimeError(
            "Rakaly stdout pipe was not created."
        )

    builder = None
    capture_prefix = None
    capture_kind = None
    capture_key = None
    capture_depth = 0

    scalar_events = {
        "string",
        "number",
        "boolean",
        "null",
    }

    def start_capture(
        prefix,
        event,
        value,
        kind,
        key,
    ):
        nonlocal builder
        nonlocal capture_prefix
        nonlocal capture_kind
        nonlocal capture_key
        nonlocal capture_depth

        builder = (
            ObjectBuilder()
        )

        builder.event(
            event,
            value,
        )

        capture_prefix = prefix
        capture_kind = kind
        capture_key = key
        capture_depth = 1


    def finish_capture(
        captured,
    ):
        nonlocal relations

        if (
            capture_kind
            == "subunit"
            and isinstance(
                captured,
                dict,
            )
        ):
            subunits[
                str(
                    capture_key
                )
            ] = captured

        elif (
            capture_kind
            == "unit"
            and isinstance(
                captured,
                dict,
            )
        ):
            units[
                str(
                    capture_key
                )
            ] = captured

            leader_id = captured.get(
                "leader"
            )

            if leader_id is not None:
                leader_ids.add(
                    str(
                        leader_id
                    )
                )

        elif (
            capture_kind
            == "character"
            and isinstance(
                captured,
                dict,
            )
        ):
            characters[
                str(
                    capture_key
                )
            ] = captured

        elif (
            capture_kind
            == "war"
            and isinstance(
                captured,
                dict,
            )
        ):
            participants = (
                captured.get(
                    "all"
                )
                or []
            )

            involved = any(
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "country"
                )
                == player_id
                and item.get(
                    "status",
                    "Active",
                )
                == "Active"
                for item in participants
            )

            if (
                involved
                and not captured.get(
                    "end_date"
                )
            ):
                player_wars.append(
                    (
                        str(
                            capture_key
                        ),
                        captured,
                    )
                )

        elif (
            capture_kind
            == "diplomacy_branch"
        ):
            for rel_path, candidate in (
                _iter_relation_candidates(
                    captured,
                    str(
                        capture_key
                    ),
                )
            ):
                if not isinstance(
                    candidate,
                    dict,
                ):
                    continue

                if not _relation_references_player(
                    candidate,
                    player_id,
                    player_tag,
                ):
                    continue

                relations.append(
                    {
                        "path": rel_path,
                        "priority": (
                            _relation_priority(
                                rel_path,
                                candidate,
                            )
                        ),
                        "country_ids": sorted(
                            _relation_country_ids(
                                candidate
                            )
                        ),
                        "data": _compact(
                            candidate
                        ),
                    }
                )


    try:

        for prefix, event, value in ijson.parse(
            process.stdout,
            use_float=True,
        ):

            if (
                prefix.startswith(
                    "countries.tags."
                )
                and event in scalar_events
            ):
                cid = (
                    prefix.rsplit(
                        ".",
                        1,
                    )[-1]
                )

                tags[
                    cid
                ] = str(
                    value
                )


            if builder is not None:

                builder.event(
                    event,
                    value,
                )

                if event in (
                    "start_map",
                    "start_array",
                ):
                    capture_depth += 1

                elif event in (
                    "end_map",
                    "end_array",
                ):
                    capture_depth -= 1


                if capture_depth == 0:
                    captured = (
                        builder.value
                    )

                    finish_capture(
                        captured
                    )

                    builder = None
                    capture_prefix = None
                    capture_kind = None
                    capture_key = None

                continue


            if event not in (
                "start_map",
                "start_array",
            ):
                continue


            if (
                include_military
                and prefix.startswith(
                    "subunit_manager.database."
                )
            ):
                sid = (
                    prefix.split(
                        ".",
                        2,
                    )[-1]
                )

                if (
                    "." not in sid
                    and sid
                    in owned_subunit_ids
                ):
                    start_capture(
                        prefix,
                        event,
                        value,
                        "subunit",
                        sid,
                    )

                    continue


            if (
                include_military
                and prefix.startswith(
                    "unit_manager.database."
                )
            ):
                uid = (
                    prefix.split(
                        ".",
                        2,
                    )[-1]
                )

                if (
                    "." not in uid
                    and uid
                    in unit_ids
                ):
                    start_capture(
                        prefix,
                        event,
                        value,
                        "unit",
                        uid,
                    )

                    continue


            if (
                include_military
                and prefix.startswith(
                    "character_db.database."
                )
            ):
                character_id = (
                    prefix.split(
                        ".",
                        2,
                    )[-1]
                )

                if (
                    "." not in character_id
                    and character_id
                    in leader_ids
                ):
                    start_capture(
                        prefix,
                        event,
                        value,
                        "character",
                        character_id,
                    )

                    continue


            if (
                include_diplomacy
                and prefix.startswith(
                    "war_manager.database."
                )
            ):
                war_id = (
                    prefix.split(
                        ".",
                        2,
                    )[-1]
                )

                if "." not in war_id:
                    start_capture(
                        prefix,
                        event,
                        value,
                        "war",
                        war_id,
                    )

                    continue


            if (
                include_diplomacy
                and prefix.startswith(
                    "diplomacy_manager."
                )
            ):
                branch = (
                    prefix.split(
                        ".",
                        1,
                    )[-1]
                )

                if "." not in branch:
                    start_capture(
                        prefix,
                        event,
                        value,
                        "diplomacy_branch",
                        branch,
                    )

                    continue


    finally:

        if process.poll() is None:
            process.terminate()

        try:
            return_code = (
                process.wait(
                    timeout=5,
                )
            )

        except subprocess.TimeoutExpired:
            process.kill()
            return_code = (
                process.wait()
            )

        stderr_text = ""

        if process.stderr is not None:
            stderr_text = (
                process.stderr
                .read()
                .decode(
                    errors="replace"
                )
                .strip()
            )


    # We deliberately terminate once parsing is complete or the stream
    # reaches EOF. A normal full read returns zero; early termination
    # can return a platform-specific nonzero code, which is harmless
    # when we already captured data.
    if (
        return_code != 0
        and not (
            subunits
            or units
            or player_wars
            or relations
        )
    ):
        raise RuntimeError(
            "Rakaly strategic-state stream failed. "
            + stderr_text[:500]
        )


    relations.sort(
        key=lambda item: (
            item[
                "priority"
            ],
            item[
                "path"
            ],
        )
    )

    # Deduplicate repeated nested candidate views.
    unique_relations = []
    seen = set()

    for relation in relations:
        signature = json.dumps(
            relation[
                "data"
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

        if signature in seen:
            continue

        seen.add(
            signature
        )

        relation = dict(
            relation
        )

        relation.pop(
            "priority",
            None,
        )

        unique_relations.append(
            relation
        )

        if len(
            unique_relations
        ) >= 30:
            break


    active_wars = [
        _summarize_war(
            war_id,
            war,
            tags,
        )
        for war_id, war
        in player_wars
    ]

    relevant_country_ids = set()

    for item in (
        (
            player_country.get(
                "rivals_2"
            )
            or []
        )
        + (
            player_country.get(
                "enemies"
            )
            or []
        )
    ):
        if (
            isinstance(
                item,
                int,
            )
        ):
            relevant_country_ids.add(
                item
            )


    for relation in unique_relations:
        for country_id in (
            relation.get(
                "country_ids",
                [],
            )
        ):
            relevant_country_ids.add(
                country_id
            )


    for war in active_wars:
        for participant in war.get(
            "participants",
            []
        ):
            country_id = participant.get(
                "country_id"
            )

            if isinstance(
                country_id,
                int,
            ):
                relevant_country_ids.add(
                    country_id
                )


    diplomacy = {
        "diplomats": (
            player_country.get(
                "diplomats"
            )
        ),
        "rivals": (
            player_country.get(
                "rivals_2"
            )
            or []
        ),
        "enemies": (
            player_country.get(
                "enemies"
            )
            or []
        ),
        "last_war": (
            player_country.get(
                "last_war"
            )
        ),
        "last_peace": (
            player_country.get(
                "last_peace"
            )
        ),
        "formal_relations": (
            unique_relations
        ),
        "active_wars": (
            active_wars
        ),
        "country_tags": {
            cid: tag
            for cid, tag
            in tags.items()
            if (
                cid.isdigit()
                and int(
                    cid
                )
                in relevant_country_ids
            )
        },
    }



    return {
        "player_id": player_id,
        "player_tag": player_tag,
        "military": (
            _summarize_military(
                player_country,
                subunits,
                units,
                characters,
            )
            if include_military
            else None
        ),
        "diplomacy": (
            diplomacy
            if include_diplomacy
            else None
        ),
        "data_note": (
            "Military data contains only the human player's owned "
            "units/subunits, unit groups and leader IDs. Diplomacy contains "
            "only player-referencing diplomacy-manager entries and wars "
            "in which the player is an active participant."
        ),
    }
