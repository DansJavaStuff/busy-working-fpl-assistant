import hashlib
import json
from itertools import combinations

from fpl_api import (
    get_bootstrap,
    get_fixtures,
    get_my_team,
    get_planning_gameweek,
)

from optimizer import (
    load_players,
    optimise_squad,
    calculate_objective_score,
    calculate_captain_score,
)

from transfer_optimizer import (
    optimise_transfers,
)

from history_store import (
    get_cached_result,
    save_cached_result,
)

from historical_analogues import (
    current_historical_analogues,
)


POST_BB_HORIZON_WEIGHT = 0.15
FIRST_HALF_END_GW = 19
SECOND_HALF_START_GW = 20
SEASON_END_GW = 38

CHIP_CACHE_MODEL_VERSION = "chip-planner-v6"
CHIP_TIMING_WINDOW_MODEL_VERSION = "chip-timing-window-v2"
CHIP_PLANNER_CACHE_TTL = 15 * 60
CHIP_OPPORTUNITY_CACHE_TTL = 30 * 60
CHIP_TIMING_WINDOW_CACHE_TTL = 12 * 60 * 60
NORMAL_TC_CANDIDATE_MAX_WINDOWS = 4
WILDCARD_HORIZON_GAMEWEEKS = 5
WILDCARD_CANDIDATE_MIN_UPLIFT = 5.0


CHIP_META = {
    "bboost": {
        "title": "Bench Boost",
        "short": "BB",
    },
    "3xc": {
        "title": "Triple Captain",
        "short": "TC",
    },
    "wildcard": {
        "title": "Wildcard",
        "short": "WC",
    },
    "freehit": {
        "title": "Free Hit",
        "short": "FH",
    },
}


def _chip_horizon_end(planning_gameweek):
    return (
        FIRST_HALF_END_GW
        if planning_gameweek <= FIRST_HALF_END_GW
        else SEASON_END_GW
    )


def _chip_boundary_status(
    card,
    gameweek,
    all_cards=None,
):
    all_cards = list(
        all_cards or [card]
    )

    if card.get("status") != "available":
        return {
            "available": False,
            "reason":
                "This chip has already been used "
                "or is not available to the entry.",
        }

    start_event = card.get(
        "start_event"
    )
    stop_event = card.get(
        "stop_event"
    )

    if (
        start_event is not None
        and gameweek < start_event
    ):
        return {
            "available": False,
            "reason":
                f"Available from GW{start_event}.",
        }

    if (
        stop_event is not None
        and gameweek > stop_event
    ):
        return {
            "available": False,
            "reason":
                f"Expired after GW{stop_event}.",
        }

    name = card.get("name")

    if (
        gameweek == 1
        and name in {
            "wildcard",
            "freehit",
        }
    ):
        return {
            "available": False,
            "reason":
                "This chip cannot be played in GW1.",
        }

    if any(
        other.get("played_event")
        == gameweek
        for other in all_cards
    ):
        return {
            "available": False,
            "reason":
                "Only one chip can be played in "
                "a Gameweek.",
        }

    if (
        name == "freehit"
        and gameweek == SECOND_HALF_START_GW
    ):
        first_half_free_hit = next(
            (
                other
                for other in all_cards
                if other.get("name")
                == "freehit"
                and other.get("number")
                == 1
            ),
            None,
        )

        if (
            first_half_free_hit is not None
            and first_half_free_hit.get(
                "played_event"
            ) == FIRST_HALF_END_GW
        ):
            return {
                "available": False,
                "reason":
                    "Free Hit cannot be played in "
                    "both GW19 and GW20.",
            }

    return {
        "available": True,
        "reason":
            "Available in this Gameweek.",
    }


def _chip_cache_context(
    planning_gameweek,
    current_team,
):
    picks = sorted(
        (
            pick["element"],
            pick.get(
                "selling_price",
                0,
            ),
            pick.get(
                "position",
                0,
            ),
        )
        for pick in current_team.get(
            "picks",
            [],
        )
    )

    transfers = current_team.get(
        "transfers",
        {},
    )

    chips = sorted(
        (
            _normalise_chip_name(
                chip
            ),
            chip.get("number"),
            _normalise_status(
                chip
            ),
            chip.get(
                "start_event"
            ),
            chip.get(
                "stop_event"
            ),
            (
                chip.get(
                    "played_by_entry"
                )
                or chip.get(
                    "played_event"
                )
            ),
        )
        for chip in current_team.get(
            "chips",
            [],
        )
    )

    return {
        "gameweek":
            planning_gameweek,
        "bank":
            transfers.get(
                "bank",
                0,
            ),
        "transfer_limit":
            transfers.get(
                "limit",
                0,
            ),
        "transfers_made":
            transfers.get(
                "made",
                0,
            ),
        "transfer_cost":
            transfers.get(
                "cost",
                0,
            ),
        "picks":
            picks,
        "chips":
            chips,
    }


def _chip_cache_key(
    planning_gameweek,
    current_team,
):
    context = _chip_cache_context(
        planning_gameweek,
        current_team,
    )

    encoded = json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _projection(player, gameweek):
    return float(
        player.get(
            f"proj_gw{gameweek}",
            0.0,
        )
        or 0.0
    )


def _fixture_context(
    players,
    gameweek,
):
    """
    Summarise the FPL fixture slate from the same
    per-team fixture counts used by player projections.
    """
    counts_by_team = {}

    for player in players:
        team_id = player.get(
            "team_id"
        )

        if (
            team_id is None
            or team_id in counts_by_team
        ):
            continue

        counts_by_team[team_id] = int(
            player.get(
                "fixture_counts",
                {},
            ).get(
                gameweek,
                0,
            )
        )

    blank_count = sum(
        count == 0
        for count in counts_by_team.values()
    )

    double_count = sum(
        count >= 2
        for count in counts_by_team.values()
    )

    if blank_count and double_count:
        kind = "blank_double"
    elif blank_count:
        kind = "blank"
    elif double_count:
        kind = "double"
    else:
        kind = "normal"

    parts = []

    if blank_count:
        parts.append(
            f"{blank_count} blank "
            f"club{'s' if blank_count != 1 else ''}"
        )

    if double_count:
        parts.append(
            f"{double_count} double "
            f"club{'s' if double_count != 1 else ''}"
        )

    label = (
        " · ".join(parts)
        if parts
        else "normal fixture slate"
    )

    return {
        "kind":
            kind,
        "blank_team_count":
            blank_count,
        "double_team_count":
            double_count,
        "label":
            label,
    }


def _fixture_certainty(
    planning_gameweek,
    gameweek,
):
    distance = max(
        0,
        int(gameweek)
        - int(planning_gameweek),
    )

    if distance == 0:
        return {
            "level": "high",
            "reason":
                "Current Gameweek fixture "
                "assignments are known.",
        }

    if distance <= 2:
        return {
            "level": "medium",
            "reason":
                "Near-term fixture assignments "
                "are useful but can still change.",
        }

    return {
        "level": "low",
        "reason":
            "Longer-range fixture assignments "
            "may change as matches are rearranged.",
    }


def _historical_evidence(
    short,
    gameweek,
    bootstrap,
    fixtures,
):
    if short not in {
        "FH",
        "BB",
        "TC",
    }:
        return None

    if (
        bootstrap is None
        or fixtures is None
    ):
        return None

    result = (
        current_historical_analogues(
            short,
            gameweek,
            limit=3,
            bootstrap=bootstrap,
            fixtures=fixtures,
        )
    )

    analogues = result.get(
        "analogues",
        [],
    )

    return {
        "current":
            result.get(
                "current",
                {},
            ),
        "analogues":
            analogues,
        "best_similarity":
            (
                analogues[0][
                    "similarity"
                ]
                if analogues
                else None
            ),
        "best":
            (
                analogues[0]
                if analogues
                else None
            ),
    }


def _chip_recommendation(
    short,
    value,
    fixture_context,
    certainty,
    historical_evidence=None,
    curve_evidence=None,
):
    kind = fixture_context.get(
        "kind",
        "normal",
    )

    if short == "WC":
        curve_evidence = (
            curve_evidence
            or {}
        )
        rank = curve_evidence.get(
            "rank"
        )
        percentile = curve_evidence.get(
            "percentile"
        )
        window_count = curve_evidence.get(
            "window_count"
        )

        if certainty["level"] == "low":
            return {
                "recommendation":
                    "HOLD",
                "model_confidence":
                    "low",
                "reason":
                    (
                        "The multi-Gameweek Wildcard "
                        "uplift is promising, but this "
                        "window is still too far away "
                        "to trust the fixture horizon."
                    ),
            }

        if (
            value >= WILDCARD_CANDIDATE_MIN_UPLIFT
            and rank is not None
            and percentile is not None
            and percentile >= 85
            and rank
            <= max(
                2,
                round(
                    (window_count or 1)
                    * 0.2
                ),
            )
        ):
            return {
                "recommendation":
                    "CANDIDATE",
                "model_confidence":
                    (
                        "high"
                        if certainty["level"]
                        == "high"
                        else "medium"
                    ),
                "reason":
                    (
                        "Wildcarding now projects a "
                        f"{value:.1f}-point gain over "
                        "the five-Gameweek no-chip "
                        "baseline and ranks near the "
                        "top of the remaining windows."
                    ),
            }

        return {
            "recommendation":
                "HOLD",
            "model_confidence":
                (
                    "medium"
                    if certainty["level"]
                    in {
                        "high",
                        "medium",
                    }
                    else "low"
                ),
            "reason":
                (
                    "The five-Gameweek Wildcard "
                    "uplift is not exceptional enough "
                    "relative to the remaining windows "
                    "to spend the chip yet."
                ),
        }

    required_kind = (
        "blank"
        if short == "FH"
        else "double"
    )

    has_structure = (
        fixture_context.get(
            "blank_team_count",
            0,
        ) > 0
        if required_kind == "blank"
        else fixture_context.get(
            "double_team_count",
            0,
        ) > 0
    )

    if not has_structure:
        curve_evidence = (
            curve_evidence
            or {}
        )
        current_rank = (
            curve_evidence.get(
                "rank"
            )
        )
        window_count = (
            curve_evidence.get(
                "window_count"
            )
        )
        percentile = (
            curve_evidence.get(
                "percentile"
            )
        )

        if (
            short == "TC"
            and certainty["level"]
            == "high"
            and current_rank == 1
            and percentile is not None
            and percentile >= 95
            and window_count is not None
            and window_count
            <= NORMAL_TC_CANDIDATE_MAX_WINDOWS
        ):
            return {
                "recommendation":
                    "CANDIDATE",
                "model_confidence":
                    "medium",
                "reason":
                    (
                        "This is the strongest "
                        "remaining modelled TC window "
                        "and only a few windows remain, "
                        "despite no Double Gameweek."
                    ),
            }

        if (
            short == "TC"
            and current_rank == 1
            and window_count
        ):
            return {
                "recommendation":
                    "HOLD",
                "model_confidence":
                    (
                        "medium"
                        if certainty["level"]
                        in {
                            "high",
                            "medium",
                        }
                        else "low"
                    ),
                "reason":
                    (
                        "This is currently the strongest "
                        f"modelled TC window (1 of "
                        f"{window_count}), but too many "
                        "future windows remain unresolved "
                        "to spend the chip on a normal "
                        "fixture slate yet."
                    ),
            }

        return {
            "recommendation":
                "HOLD",
            "model_confidence":
                (
                    "medium"
                    if certainty["level"]
                    in {
                        "high",
                        "medium",
                    }
                    else "low"
                ),
            "reason":
                (
                    "No relevant "
                    f"{required_kind} fixture "
                    "pattern is currently assigned."
                ),
        }

    best_similarity = (
        historical_evidence or {}
    ).get(
        "best_similarity"
    )

    if best_similarity is None:
        return {
            "recommendation":
                "HOLD",
            "model_confidence":
                "low",
            "reason":
                (
                    "A special fixture pattern "
                    "exists, but there is no "
                    "applicable historical analogue "
                    "yet."
                ),
        }

    if certainty["level"] == "low":
        return {
            "recommendation":
                "HOLD",
            "model_confidence":
                "low",
            "reason":
                (
                    "The fixture pattern is "
                    "promising but still too "
                    "far away to trust."
                ),
        }

    if (
        best_similarity >= 80
        and value > 0
    ):
        return {
            "recommendation":
                "CANDIDATE",
            "model_confidence":
                (
                    "high"
                    if certainty["level"]
                    == "high"
                    else "medium"
                ),
            "reason":
                (
                    "Positive model value plus "
                    "a strong historical pattern "
                    "match. Keep under review."
                ),
        }

    return {
        "recommendation":
            "HOLD",
        "model_confidence":
            "medium",
        "reason":
            (
                "The special fixture shape is "
                "present, but historical support "
                "is not strong enough yet."
            ),
    }


def _normalise_status(chip):
    status = (
        chip.get("status_for_entry")
        or chip.get("status")
        or ""
    ).lower()

    if status in {
        "available",
        "active",
    }:
        return "available"

    if status in {
        "played",
        "used",
        "unavailable",
    }:
        return "used"

    return "unknown"


def _normalise_chip_name(chip):
    name = (
        chip.get("name")
        or chip.get("chip_name")
        or ""
    ).lower()

    aliases = {
        "bench_boost": "bboost",
        "benchboost": "bboost",
        "triple_captain": "3xc",
        "triplecaptain": "3xc",
        "free_hit": "freehit",
        "free_hit_chip": "freehit",
        "wc": "wildcard",
    }

    return aliases.get(
        name,
        name,
    )


def _chip_cards(
    current_team,
    planning_gameweek=None,
):
    raw_chips = current_team.get(
        "chips",
        [],
    )

    cards = []

    for chip in raw_chips:
        name = _normalise_chip_name(
            chip
        )

        meta = CHIP_META.get(
            name,
            {
                "title":
                    name.replace(
                        "_",
                        " ",
                    ).title()
                    or "Chip",
                "short":
                    name.upper()
                    or "?",
            },
        )

        cards.append({
            "name":
                name,
            "title":
                meta["title"],
            "short":
                meta["short"],
            "status":
                _normalise_status(
                    chip
                ),
            "number":
                chip.get(
                    "number"
                ),
            "start_event":
                chip.get(
                    "start_event"
                ),
            "stop_event":
                chip.get(
                    "stop_event"
                ),
            "played_event":
                chip.get(
                    "played_by_entry"
                )
                or chip.get(
                    "played_event"
                ),
            "raw":
                chip,
        })

    if planning_gameweek is not None:
        for card in cards:
            boundary = (
                _chip_boundary_status(
                    card,
                    planning_gameweek,
                    cards,
                )
            )
            card["available_now"] = (
                boundary["available"]
            )
            card["availability_reason"] = (
                boundary["reason"]
            )

    return cards


def _post_bb_projection(
    player,
    planning_gameweek,
):
    return sum(
        _projection(
            player,
            gameweek,
        )
        for gameweek in range(
            planning_gameweek + 1,
            planning_gameweek + 5,
        )
    )


def _formation(starters):
    counts = {
        "DEF": 0,
        "MID": 0,
        "FWD": 0,
    }

    for player in starters:
        position = player.get(
            "position"
        )

        if position in counts:
            counts[position] += 1

    return (
        f"{counts['DEF']}-"
        f"{counts['MID']}-"
        f"{counts['FWD']}"
    )


def _pair_transfers(result):
    remaining = list(
        result.get(
            "incoming",
            [],
        )
    )

    pairs = []

    for outgoing in sorted(
        result.get(
            "outgoing",
            [],
        ),
        key=lambda p:
            p["position_id"],
    ):
        incoming = next(
            (
                player
                for player in remaining
                if player["position"]
                == outgoing["position"]
            ),
            None,
        )

        if incoming is None:
            continue

        remaining.remove(
            incoming
        )

        pairs.append({
            "out":
                outgoing["name"],
            "in":
                incoming["name"],
        })

    return pairs


def _normal_gw_projection(
    result,
    planning_gameweek,
):
    starters = [
        player
        for player in result["squad"]
        if player["starter"]
    ]

    captain = next(
        player
        for player in starters
        if player["captain"]
    )

    gross = (
        sum(
            _projection(
                player,
                planning_gameweek,
            )
            for player in starters
        )
        +
        _projection(
            captain,
            planning_gameweek,
        )
    )

    return (
        gross
        - result["hit_cost"]
    )


def _bench_boost_scenarios(
    players,
    current_team,
    planning_gameweek,
    normal_scenarios=None,
):
    scenarios = []

    for transfers in range(0, 4):
        result = optimise_transfers(
            players,
            current_team,
            planning_gameweek,
            transfers,
            chip_mode="bench_boost",
        )

        normal_result = next(
            (
                scenario
                for scenario in (
                    normal_scenarios or []
                )
                if scenario["transfers"]
                == transfers
            ),
            None,
        )

        if normal_result is None:
            normal_result = optimise_transfers(
                players,
                current_team,
                planning_gameweek,
                transfers,
            )

        if (
            result is None
            or
            normal_result is None
        ):
            continue

        squad = result["squad"]

        starters = [
            player
            for player in squad
            if player["starter"]
        ]

        bench = [
            player
            for player in squad
            if not player["starter"]
        ]

        captain = next(
            player
            for player in starters
            if player["captain"]
        )

        squad_projection = sum(
            _projection(
                player,
                planning_gameweek,
            )
            for player in squad
        )

        captain_projection = (
            _projection(
                captain,
                planning_gameweek,
            )
        )

        bench_projection = sum(
            _projection(
                player,
                planning_gameweek,
            )
            for player in bench
        )

        post_bb_projection = sum(
            _post_bb_projection(
                player,
                planning_gameweek,
            )
            for player in squad
        )

        normal_post_projection = sum(
            _post_bb_projection(
                player,
                planning_gameweek,
            )
            for player
            in normal_result["squad"]
        )

        gross_projection = (
            squad_projection
            + captain_projection
        )

        net_projection = (
            gross_projection
            - result["hit_cost"]
        )

        normal_net_projection = (
            _normal_gw_projection(
                normal_result,
                planning_gameweek,
            )
        )

        bb_uplift = (
            net_projection
            - normal_net_projection
        )

        scenarios.append({
            "transfers":
                transfers,
            "hit_cost":
                result["hit_cost"],
            "gross_projection":
                gross_projection,
            "net_projection":
                net_projection,
            "bench_projection":
                bench_projection,
            "normal_net_projection":
                normal_net_projection,
            "bb_uplift":
                bb_uplift,
            "formation":
                _formation(
                    starters
                ),
            "post_bb_projection":
                post_bb_projection,
            "normal_post_projection":
                normal_post_projection,
            "pairs":
                _pair_transfers(
                    result
                ),
            "normal_pairs":
                _pair_transfers(
                    normal_result
                ),
        })

    if not scenarios:
        return {
            "scenarios": [],
            "baseline": None,
            "best": None,
            "best_practical": None,
            "best_uplift": None,
            "best_no_hit": None,
        }

    baseline = next(
        (
            scenario
            for scenario in scenarios
            if scenario["transfers"] == 0
        ),
        scenarios[0],
    )

    for scenario in scenarios:
        scenario["gain_vs_current"] = (
            scenario["net_projection"]
            - baseline["net_projection"]
        )

        scenario["post_bb_delta"] = (
            scenario["post_bb_projection"]
            - baseline["post_bb_projection"]
        )

        scenario["post_vs_normal_delta"] = (
            scenario["post_bb_projection"]
            - scenario["normal_post_projection"]
        )

        scenario["practical_gain"] = (
            scenario["bb_uplift"]
            +
            (
                scenario["post_vs_normal_delta"]
                * POST_BB_HORIZON_WEIGHT
            )
        )

        scenario["practical_score"] = (
            scenario["practical_gain"]
        )

        scenario["rental_risk"] = (
            scenario["bb_uplift"] > 0
            and
            scenario["post_vs_normal_delta"] < 0
        )

    best = max(
        scenarios,
        key=lambda item:
            item["net_projection"],
    )

    best_practical = max(
        scenarios,
        key=lambda item:
            item["practical_score"],
    )

    best_uplift = max(
        scenarios,
        key=lambda item:
            item["bb_uplift"],
    )

    no_hit = [
        scenario
        for scenario in scenarios
        if scenario["hit_cost"] == 0
    ]

    best_no_hit = (
        max(
            no_hit,
            key=lambda item:
                item["net_projection"],
        )
        if no_hit
        else None
    )

    return {
        "scenarios":
            scenarios,
        "baseline":
            baseline,
        "best":
            best,
        "best_practical":
            best_practical,
        "best_uplift":
            best_uplift,
        "best_no_hit":
            best_no_hit,
    }


def _tc_candidate_score(
    player,
    gameweek,
):
    """
    Ranking score for Triple Captain candidates.

    Expected points remains the main input, but
    captaincy should slightly favour attacking
    positions and penalise defensive/GK variance.
    """

    projection = _projection(
        player,
        gameweek,
    )

    position_multiplier = {
        "FWD": 1.08,
        "MID": 1.05,
        "DEF": 0.94,
        "GKP": 0.88,
    }.get(
        player.get("position"),
        1.0,
    )

    return (
        projection
        * position_multiplier
    )


def _triple_captain_windows(
    players,
    current_team,
    planning_gameweek,
    end_gameweek,
):
    current_ids = {
        pick["element"]
        for pick in current_team.get(
            "picks",
            [],
        )
    }

    windows = []

    for gameweek in range(
        planning_gameweek,
        end_gameweek + 1,
    ):
        league_candidates = sorted(
            (
                {
                    "id":
                        player["id"],
                    "name":
                        player["name"],
                    "team":
                        player["team"],
                    "position":
                        player["position"],
                    "projection":
                        _projection(
                            player,
                            gameweek,
                        ),
                    "captain_score":
                        _tc_candidate_score(
                            player,
                            gameweek,
                        ),
                    "owned":
                        player["id"]
                        in current_ids,
                }
                for player in players
                if player.get(
                    "can_select",
                    True,
                )
                and
                _projection(
                    player,
                    gameweek,
                ) > 0
            ),
            key=lambda item:
                item["captain_score"],
            reverse=True,
        )

        owned_candidates = [
            candidate
            for candidate
            in league_candidates
            if candidate["owned"]
        ]

        if (
            not league_candidates
            or
            not owned_candidates
        ):
            continue

        best_league = (
            league_candidates[0]
        )
        best_owned = (
            owned_candidates[0]
        )

        windows.append({
            "gameweek":
                gameweek,
            "fixture_context":
                _fixture_context(
                    players,
                    gameweek,
                ),
            "owned_captain":
                best_owned,
            "best_candidate":
                best_league,
            "best_is_owned":
                best_league["owned"],
            "owned_tc_uplift":
                best_owned["projection"],
            "best_tc_uplift":
                best_league["projection"],
            "transfer_gap":
                (
                    best_league["projection"]
                    - best_owned["projection"]
                ),
            "alternatives":
                league_candidates[1:3],
        })

    if not windows:
        return {
            "windows": [],
            "best": None,
            "best_owned": None,
        }

    best = max(
        windows,
        key=lambda item:
            item["best_tc_uplift"],
    )

    best_owned = max(
        windows,
        key=lambda item:
            item["owned_tc_uplift"],
    )

    for window in windows:
        window["gap_to_best"] = (
            window["best_tc_uplift"]
            - best["best_tc_uplift"]
        )

    return {
        "windows":
            windows,
        "best":
            best,
        "best_owned":
            best_owned,
    }


def _normal_scenarios(
    players,
    current_team,
    planning_gameweek,
    max_transfers=3,
):
    scenarios = []

    for transfers in range(
        0,
        max_transfers + 1,
    ):
        result = optimise_transfers(
            players,
            current_team,
            planning_gameweek,
            transfers,
        )

        if result is None:
            continue

        result = result.copy()
        result["gw_projection"] = (
            _normal_gw_projection(
                result,
                planning_gameweek,
            )
        )

        scenarios.append(
            result
        )

    return scenarios


def _best_normal_scenario(
    players,
    current_team,
    planning_gameweek,
    max_transfers=3,
    normal_scenarios=None,
):
    scenarios = (
        normal_scenarios
        if normal_scenarios is not None
        else _normal_scenarios(
            players,
            current_team,
            planning_gameweek,
            max_transfers,
        )
    )

    if not scenarios:
        return None

    return max(
        scenarios,
        key=lambda item:
            item["net_score"],
    )


def _free_hit_analysis(
    players,
    current_team,
    planning_gameweek,
    normal_scenarios=None,
):
    picks = current_team.get(
        "picks",
        [],
    )

    budget = (
        sum(
            pick["selling_price"]
            for pick in picks
        )
        +
        current_team[
            "transfers"
        ]["bank"]
    )

    normal = _best_normal_scenario(
        players,
        current_team,
        planning_gameweek,
        normal_scenarios=
            normal_scenarios,
    )

    free_hit_squad = optimise_squad(
        players,
        budget_limit=budget,
        objective_mode="free_hit",
    )

    starters = [
        player
        for player in free_hit_squad
        if player["starter"]
    ]

    captain = next(
        player
        for player in starters
        if player["captain"]
    )

    free_hit_gw = (
        sum(
            _projection(
                player,
                planning_gameweek,
            )
            for player in starters
        )
        +
        _projection(
            captain,
            planning_gameweek,
        )
    )

    current_ids = {
        pick["element"]
        for pick in picks
    }

    fh_ids = {
        player["id"]
        for player in free_hit_squad
    }

    players_by_id = {
        player["id"]: player
        for player in players
    }

    outgoing = [
        players_by_id[player_id]
        for player_id in current_ids
        if player_id not in fh_ids
    ]

    incoming = [
        player
        for player in free_hit_squad
        if player["id"]
        not in current_ids
    ]

    return {
        "budget":
            budget,
        "normal":
            normal,
        "normal_gw":
            (
                normal["gw_projection"]
                if normal
                else None
            ),
        "free_hit_gw":
            free_hit_gw,
        "uplift":
            (
                free_hit_gw
                - normal["gw_projection"]
                if normal
                else None
            ),
        "changes":
            len(incoming),
        "outgoing":
            sorted(
                outgoing,
                key=lambda p:
                    (
                        p["position_id"],
                        p["name"],
                    ),
            ),
        "incoming":
            sorted(
                incoming,
                key=lambda p:
                    (
                        p["position_id"],
                        p["name"],
                    ),
            ),
        "squad":
            free_hit_squad,
    }


def _wildcard_analysis(
    players,
    current_team,
    planning_gameweek,
    normal_scenarios=None,
):
    picks = current_team.get(
        "picks",
        [],
    )

    current_ids = {
        pick["element"]
        for pick in picks
    }

    budget = (
        sum(
            pick["selling_price"]
            for pick in picks
        )
        +
        current_team[
            "transfers"
        ]["bank"]
    )

    current_result = next(
        (
            scenario
            for scenario in (
                normal_scenarios or []
            )
            if scenario["transfers"] == 0
        ),
        None,
    )

    if current_result is None:
        current_result = optimise_transfers(
            players,
            current_team,
            planning_gameweek,
            0,
        )

    best_normal = _best_normal_scenario(
        players,
        current_team,
        planning_gameweek,
        normal_scenarios=
            normal_scenarios,
    )

    wildcard_squad = optimise_squad(
        players,
        budget_limit=budget,
    )

    current_score = (
        calculate_objective_score(
            current_result["squad"]
        )
    )

    wildcard_score = (
        calculate_objective_score(
            wildcard_squad
        )
    )

    wildcard_ids = {
        player["id"]
        for player in wildcard_squad
    }

    outgoing = [
        player
        for player in current_result["squad"]
        if player["id"]
        not in wildcard_ids
    ]

    incoming = [
        player
        for player in wildcard_squad
        if player["id"]
        not in current_ids
    ]

    current_gw = (
        _normal_gw_projection(
            current_result,
            planning_gameweek,
        )
    )

    wildcard_starters = [
        player
        for player in wildcard_squad
        if player["starter"]
    ]

    wildcard_captain = next(
        player
        for player in wildcard_starters
        if player["captain"]
    )

    wildcard_gw = (
        sum(
            _projection(
                player,
                planning_gameweek,
            )
            for player
            in wildcard_starters
        )
        +
        _projection(
            wildcard_captain,
            planning_gameweek,
        )
    )

    normal_score = (
        best_normal["net_score"]
        if best_normal
        else current_score
    )

    normal_gw = (
        best_normal["gw_projection"]
        if best_normal
        else current_gw
    )

    return {
        "budget":
            budget,
        "best_normal":
            best_normal,
        "normal_score":
            normal_score,
        "normal_gw":
            normal_gw,
        "normal_transfers":
            (
                best_normal["transfers"]
                if best_normal
                else 0
            ),
        "normal_hit":
            (
                best_normal["hit_cost"]
                if best_normal
                else 0
            ),
        "current_score":
            current_score,
        "wildcard_score":
            wildcard_score,
        "objective_uplift":
            (
                wildcard_score
                - normal_score
            ),
        "current_gw":
            current_gw,
        "wildcard_gw":
            wildcard_gw,
        "gw_uplift":
            (
                wildcard_gw
                - normal_gw
            ),
        "changes":
            len(incoming),
        "outgoing":
            sorted(
                outgoing,
                key=lambda p:
                    (
                        p["position_id"],
                        p["name"],
                    ),
            ),
        "incoming":
            sorted(
                incoming,
                key=lambda p:
                    (
                        p["position_id"],
                        p["name"],
                    ),
            ),
        "squad":
            wildcard_squad,
    }


def _current_squad_lineup(
    players,
    current_team,
    gameweek,
):
    """
    Pick the best XI/captain from the 15 players already
    owned without invoking CBC.

    For a zero-transfer timing window the selected squad is
    fixed, so the multi-GW selected-player term in the MILP
    objective is constant. Exhaustively checking the tiny
    set of possible starting XIs is therefore equivalent for
    the GW/captain decision and far cheaper than solving over
    the full player pool.
    """
    players_by_id = {
        player["id"]: player
        for player in players
    }

    squad = []

    for pick in current_team.get(
        "picks",
        [],
    ):
        player = players_by_id.get(
            pick.get("element")
        )

        if player is None:
            return None

        squad.append(
            player.copy()
        )

    if len(squad) != 15:
        return None

    best = None
    best_score = None

    for starter_indices in combinations(
        range(len(squad)),
        11,
    ):
        starter_set = set(
            starter_indices
        )
        starters = [
            squad[index]
            for index in starter_indices
        ]

        position_counts = {
            "GKP": 0,
            "DEF": 0,
            "MID": 0,
            "FWD": 0,
        }

        for player in starters:
            position = player.get(
                "position"
            )
            if position in position_counts:
                position_counts[
                    position
                ] += 1

        if position_counts["GKP"] != 1:
            continue
        if position_counts["DEF"] < 3:
            continue
        if position_counts["MID"] < 2:
            continue
        if position_counts["FWD"] < 1:
            continue

        captain = max(
            starters,
            key=calculate_captain_score,
        )

        score = (
            sum(
                _projection(
                    player,
                    gameweek,
                )
                for player in starters
            )
            + calculate_captain_score(
                captain
            )
        )

        if (
            best_score is None
            or score > best_score
        ):
            best_score = score
            best = (
                starter_set,
                captain["id"],
            )

    if best is None:
        return None

    starter_set, captain_id = best
    result_squad = []

    for index, player in enumerate(
        squad
    ):
        item = player.copy()
        item["starter"] = (
            index in starter_set
        )
        item["captain"] = (
            item["id"] == captain_id
        )
        result_squad.append(
            item
        )

    return {
        "squad":
            result_squad,
        "hit_cost":
            0,
        "transfers":
            0,
    }


def _team_for_fixed_squad(
    squad,
):
    return {
        "picks": [
            {
                "element":
                    player["id"],
                "selling_price":
                    player.get(
                        "cost",
                        0,
                    ),
            }
            for player in squad
        ],
        "transfers": {
            "bank": 0,
            "limit": 1,
            "made": 0,
            "cost": 4,
        },
    }


def _fixed_squad_horizon_score(
    players,
    squad,
    start_gameweek,
    end_gameweek,
):
    horizon_end = min(
        end_gameweek,
        start_gameweek
        + WILDCARD_HORIZON_GAMEWEEKS
        - 1,
    )
    team = _team_for_fixed_squad(
        squad
    )
    total = 0.0
    weekly = []

    for gameweek in range(
        start_gameweek,
        horizon_end + 1,
    ):
        anchored = _players_at_gameweek(
            players,
            gameweek,
            end_gameweek,
        )
        lineup = _current_squad_lineup(
            anchored,
            team,
            gameweek,
        )

        if lineup is None:
            return None

        score = _normal_gw_projection(
            lineup,
            gameweek,
        )
        total += score
        weekly.append({
            "gameweek":
                gameweek,
            "score":
                score,
        })

    return {
        "score":
            total,
        "weekly":
            weekly,
        "start_gameweek":
            start_gameweek,
        "end_gameweek":
            horizon_end,
        "gameweeks":
            len(weekly),
    }


def _wildcard_multiweek_value(
    players,
    anchored,
    team,
    wildcard_squad,
    gameweek,
    end_gameweek,
):
    hold_squad = (
        _current_squad_lineup(
            anchored,
            team,
            gameweek,
        )
    )

    if hold_squad is None:
        return None

    baseline_squad = (
        hold_squad["squad"]
    )
    baseline_type = "hold"

    one_transfer = optimise_transfers(
        anchored,
        team,
        gameweek,
        1,
    )

    if one_transfer is not None:
        hold_horizon = (
            _fixed_squad_horizon_score(
                players,
                baseline_squad,
                gameweek,
                end_gameweek,
            )
        )
        transfer_horizon = (
            _fixed_squad_horizon_score(
                players,
                one_transfer["squad"],
                gameweek,
                end_gameweek,
            )
        )

        if (
            hold_horizon is not None
            and transfer_horizon
            is not None
            and transfer_horizon["score"]
            > hold_horizon["score"]
        ):
            baseline_squad = (
                one_transfer["squad"]
            )
            baseline_type = (
                "one_free_transfer"
            )

    baseline = (
        _fixed_squad_horizon_score(
            players,
            baseline_squad,
            gameweek,
            end_gameweek,
        )
    )
    wildcard = (
        _fixed_squad_horizon_score(
            players,
            wildcard_squad,
            gameweek,
            end_gameweek,
        )
    )

    if (
        baseline is None
        or wildcard is None
    ):
        return None

    return {
        "value":
            wildcard["score"]
            - baseline["score"],
        "baseline_score":
            baseline["score"],
        "wildcard_score":
            wildcard["score"],
        "baseline_type":
            baseline_type,
        "gameweeks":
            wildcard["gameweeks"],
        "end_gameweek":
            wildcard["end_gameweek"],
        "baseline_weekly":
            baseline["weekly"],
        "wildcard_weekly":
            wildcard["weekly"],
    }


def _timing_window_cache_key(
    players,
    current_team,
    gameweek,
    end_gameweek,
):
    projection_rows = []

    for player in players:
        projection_rows.append({
            "id":
                player.get("id"),
            "cost":
                player.get("cost"),
            "can_select":
                player.get(
                    "can_select",
                    True,
                ),
            "gw":
                round(
                    _projection(
                        player,
                        gameweek,
                    ),
                    4,
                ),
            "horizon":
                [
                    round(
                        _projection(
                            player,
                            gw,
                        ),
                        4,
                    )
                    for gw in range(
                        gameweek,
                        min(
                            end_gameweek,
                            gameweek + 4,
                        ) + 1,
                    )
                ],
        })

    payload = {
        "gameweek":
            int(gameweek),
        "end_gameweek":
            int(end_gameweek),
        "team":
            _chip_cache_context(
                gameweek,
                _future_team_state(
                    current_team
                ),
            ),
        "players":
            projection_rows,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _players_at_gameweek(
    players,
    gameweek,
    end_gameweek,
):
    """
    Re-anchor already-calculated player projections
    to a future planning Gameweek without another
    FPL/API data load.
    """

    anchored = []

    for player in players:
        item = player.copy()
        item["planning_gameweek"] = gameweek
        item["proj_next"] = _projection(
            player,
            gameweek,
        )
        item["proj_5gw"] = sum(
            _projection(
                player,
                gw,
            )
            for gw in range(
                gameweek,
                min(
                    end_gameweek,
                    gameweek + 4,
                ) + 1,
            )
        )
        anchored.append(item)

    return anchored


def _future_team_state(
    current_team,
):
    """
    Future chip windows are a timing snapshot, not
    a prediction of transfer accumulation. Keep the
    current squad/prices/bank and use a neutral one
    free-transfer state for any helper that needs it.
    """

    team = {
        **current_team,
        "picks": [
            pick.copy()
            for pick
            in current_team.get(
                "picks",
                [],
            )
        ],
        "transfers": {
            **current_team.get(
                "transfers",
                {},
            ),
            "limit": 1,
            "made": 0,
        },
    }

    return team


def _timing_window(
    players,
    current_team,
    gameweek,
    end_gameweek,
    force_refresh=False,
):
    cache_key = (
        _timing_window_cache_key(
            players,
            current_team,
            gameweek,
            end_gameweek,
        )
    )

    if not force_refresh:
        cached = get_cached_result(
            "chip_timing_window",
            cache_key,
            CHIP_TIMING_WINDOW_MODEL_VERSION,
        )

        if cached is not None:
            return cached

    anchored = _players_at_gameweek(
        players,
        gameweek,
        end_gameweek,
    )

    team = _future_team_state(
        current_team
    )

    hold = _current_squad_lineup(
        anchored,
        team,
        gameweek,
    )

    if hold is None:
        return None

    hold_gw = _normal_gw_projection(
        hold,
        gameweek,
    )

    bench = [
        player
        for player in hold["squad"]
        if not player["starter"]
    ]

    bb_value = sum(
        _projection(
            player,
            gameweek,
        )
        for player in bench
    )

    budget = (
        sum(
            pick["selling_price"]
            for pick in team.get(
                "picks",
                [],
            )
        )
        +
        team["transfers"]["bank"]
    )

    wildcard_squad = optimise_squad(
        anchored,
        budget_limit=budget,
    )

    wc_starters = [
        player
        for player in wildcard_squad
        if player["starter"]
    ]

    wc_captain = next(
        player
        for player in wc_starters
        if player["captain"]
    )

    wildcard_gw = (
        sum(
            _projection(
                player,
                gameweek,
            )
            for player in wc_starters
        )
        +
        _projection(
            wc_captain,
            gameweek,
        )
    )

    wildcard_multiweek = (
        _wildcard_multiweek_value(
            players,
            anchored,
            team,
            wildcard_squad,
            gameweek,
            end_gameweek,
        )
    )

    free_hit_squad = optimise_squad(
        anchored,
        budget_limit=budget,
        objective_mode="free_hit",
    )

    fh_starters = [
        player
        for player in free_hit_squad
        if player["starter"]
    ]

    fh_captain = next(
        player
        for player in fh_starters
        if player["captain"]
    )

    free_hit_gw = (
        sum(
            _projection(
                player,
                gameweek,
            )
            for player in fh_starters
        )
        +
        _projection(
            fh_captain,
            gameweek,
        )
    )

    result = {
        "gameweek": gameweek,
        "fixture_context":
            _fixture_context(
                players,
                gameweek,
            ),
        "hold_gw": hold_gw,
        "bb_value": bb_value,
        "wc_value":
            (
                wildcard_multiweek[
                    "value"
                ]
                if wildcard_multiweek
                is not None
                else wildcard_gw
                - hold_gw
            ),
        "wc_horizon":
            wildcard_multiweek,
        "wc_gw_value":
            wildcard_gw
            - hold_gw,
        "fh_value":
            free_hit_gw - hold_gw,
    }

    save_cached_result(
        "chip_timing_window",
        cache_key,
        CHIP_TIMING_WINDOW_MODEL_VERSION,
        result,
        CHIP_TIMING_WINDOW_CACHE_TTL,
    )

    return result


def _future_chip_windows(
    players,
    current_team,
    planning_gameweek,
    end_gameweek,
    force_refresh=False,
):
    windows = []

    for gameweek in range(
        planning_gameweek,
        end_gameweek + 1,
    ):
        window = _timing_window(
            players,
            current_team,
            gameweek,
            end_gameweek,
            force_refresh=force_refresh,
        )

        if window is not None:
            windows.append(window)

    return windows


def _build_timing_curve(
    short,
    windows,
    value_key,
    planning_gameweek,
):
    points = []

    for window in windows:
        value = float(
            window.get(
                value_key,
                0.0,
            )
            or 0.0
        )

        fixture_context = (
            window.get(
                "fixture_context",
                {},
            )
            or {}
        )

        points.append({
            "gameweek":
                int(
                    window["gameweek"]
                ),
            "value":
                value,
            "fixture_label":
                fixture_context.get(
                    "label",
                    "fixture slate unknown",
                ),
            "fixture_kind":
                fixture_context.get(
                    "kind",
                    "normal",
                ),
            "certainty":
                _fixture_certainty(
                    planning_gameweek,
                    window["gameweek"],
                )["level"],
            "current":
                int(
                    window["gameweek"]
                ) == int(
                    planning_gameweek
                ),
        })

    if not points:
        return {
            "short": short,
            "points": [],
            "best_gameweek": None,
            "best_value": None,
            "current_rank": None,
            "window_count": 0,
            "current_percentile": None,
        }

    best_value = max(
        point["value"]
        for point in points
    )

    current_point = next(
        (
            point
            for point in points
            if point["current"]
        ),
        None,
    )

    ranked_values = sorted(
        (
            point["value"]
            for point in points
        ),
        reverse=True,
    )

    current_rank = None
    current_percentile = None

    if current_point is not None:
        current_value = (
            current_point["value"]
        )
        current_rank = (
            1
            + sum(
                value > current_value
                for value
                in ranked_values
            )
        )
        current_percentile = round(
            100
            * sum(
                value <= current_value
                for value
                in ranked_values
            )
            / len(
                ranked_values
            ),
            1,
        )

    positive_peak = max(
        best_value,
        0.0,
    )

    for point in points:
        if positive_peak <= 0:
            point["bar_height"] = 8.0
        else:
            point["bar_height"] = round(
                max(
                    8.0,
                    min(
                        100.0,
                        100
                        * max(
                            0.0,
                            point["value"],
                        )
                        / positive_peak,
                    ),
                ),
                1,
            )

        point["best"] = (
            point["value"]
            == best_value
        )

    best_point = next(
        point
        for point in points
        if point["best"]
    )

    for point in points:
        point_value = point["value"]
        point["rank"] = (
            1
            + sum(
                value > point_value
                for value in ranked_values
            )
        )
        point["percentile"] = round(
            100
            * sum(
                value <= point_value
                for value in ranked_values
            )
            / len(ranked_values),
            1,
        )

    return {
        "short": short,
        "points": points,
        "best_gameweek":
            best_point[
                "gameweek"
            ],
        "best_value":
            best_value,
        "current_rank":
            current_rank,
        "window_count":
            len(points),
        "current_percentile":
            current_percentile,
    }


def _chip_timing_curves(
    planning_gameweek,
    timing_windows,
    triple_captain,
):
    tc_windows = (
        triple_captain.get(
            "windows",
            [],
        )
    )

    return [
        _build_timing_curve(
            "BB",
            timing_windows,
            "bb_value",
            planning_gameweek,
        ),
        _build_timing_curve(
            "TC",
            tc_windows,
            "best_tc_uplift",
            planning_gameweek,
        ),
        _build_timing_curve(
            "WC",
            timing_windows,
            "wc_value",
            planning_gameweek,
        ),
        _build_timing_curve(
            "FH",
            timing_windows,
            "fh_value",
            planning_gameweek,
        ),
    ]


def _chip_opportunity_summary(
    planning_gameweek,
    bench_boost,
    triple_captain,
    wildcard,
    free_hit,
    timing_windows,
    bootstrap=None,
    fixtures=None,
):
    rows = []

    curves = _chip_timing_curves(
        planning_gameweek,
        timing_windows,
        triple_captain,
    )
    curves_by_short = {
        curve["short"]: curve
        for curve in curves
    }

    def curve_evidence_for(
        short,
        gameweek,
    ):
        curve = curves_by_short.get(
            short,
            {}
        )
        point = next(
            (
                item
                for item in curve.get(
                    "points",
                    [],
                )
                if item["gameweek"]
                == gameweek
            ),
            None,
        )
        if point is None:
            return None
        return {
            "rank":
                point.get("rank"),
            "percentile":
                point.get(
                    "percentile"
                ),
            "window_count":
                curve.get(
                    "window_count"
                ),
        }

    current_timing = next(
        (
            window
            for window in timing_windows
            if window["gameweek"]
            == planning_gameweek
        ),
        None,
    )

    future_timing = [
        window
        for window in timing_windows
        if window["gameweek"]
        > planning_gameweek
    ]

    def add_timing_row(
        chip,
        short,
        key,
        context,
    ):
        if current_timing is None:
            return

        now_value = current_timing[key]

        later = (
            max(
                future_timing,
                key=lambda item:
                    item[key],
            )
            if future_timing
            else None
        )

        later_value = (
            later[key]
            if later
            else None
        )

        now_certainty = _fixture_certainty(
            planning_gameweek,
            planning_gameweek,
        )
        now_history = _historical_evidence(
            short,
            planning_gameweek,
            bootstrap,
            fixtures,
        )
        decision = _chip_recommendation(
            short,
            now_value,
            current_timing[
                "fixture_context"
            ],
            now_certainty,
            now_history,
            curve_evidence_for(
                short,
                planning_gameweek,
            ),
        )

        later_certainty = (
            _fixture_certainty(
                planning_gameweek,
                later["gameweek"],
            )
            if later
            else None
        )
        later_history = (
            _historical_evidence(
                short,
                later["gameweek"],
                bootstrap,
                fixtures,
            )
            if later
            else None
        )
        later_decision = (
            _chip_recommendation(
                short,
                later_value,
                later["fixture_context"],
                later_certainty,
                later_history,
            )
            if later
            else None
        )

        rows.append({
            "chip": chip,
            "short": short,
            "now_value": now_value,
            "now_context":
                (
                    f"{context} · "
                    f"{current_timing['fixture_context']['label']}"
                ),
            "best_later_fixture_context":
                (
                    later["fixture_context"]["label"]
                    if later
                    else None
                ),
            "best_later_value":
                later_value,
            "best_later_gw":
                (
                    later["gameweek"]
                    if later
                    else None
                ),
            "cost_of_waiting":
                (
                    now_value
                    - later_value
                    if later_value
                    is not None
                    else None
                ),
            "status": "comparable",
            "recommendation":
                decision["recommendation"],
            "recommendation_reason":
                decision["reason"],
            "fixture_certainty":
                now_certainty["level"],
            "fixture_certainty_reason":
                now_certainty["reason"],
            "model_confidence":
                decision["model_confidence"],
            "historical":
                now_history,
            "best_later_fixture_certainty":
                (
                    later_certainty["level"]
                    if later_certainty
                    else None
                ),
            "best_later_historical":
                later_history,
            "best_later_recommendation":
                (
                    later_decision[
                        "recommendation"
                    ]
                    if later_decision
                    else None
                ),
            "best_later_model_confidence":
                (
                    later_decision[
                        "model_confidence"
                    ]
                    if later_decision
                    else None
                ),
            "best_later_recommendation_reason":
                (
                    later_decision[
                        "reason"
                    ]
                    if later_decision
                    else None
                ),
        })

    add_timing_row(
        "Bench Boost",
        "BB",
        "bb_value",
        "current squad baseline",
    )

    tc_windows = triple_captain.get(
        "windows",
        [],
    )

    current_tc = next(
        (
            window
            for window in tc_windows
            if window["gameweek"]
            == planning_gameweek
        ),
        None,
    )

    later_tc = [
        window
        for window in tc_windows
        if window["gameweek"]
        > planning_gameweek
    ]

    best_later_tc = (
        max(
            later_tc,
            key=lambda item:
                item["best_tc_uplift"],
        )
        if later_tc
        else None
    )

    if current_tc is not None:
        now_value = (
            current_tc[
                "best_tc_uplift"
            ]
        )

        later_value = (
            best_later_tc[
                "best_tc_uplift"
            ]
            if best_later_tc
            else None
        )

        now_certainty = _fixture_certainty(
            planning_gameweek,
            planning_gameweek,
        )
        now_history = _historical_evidence(
            "TC",
            planning_gameweek,
            bootstrap,
            fixtures,
        )
        decision = _chip_recommendation(
            "TC",
            now_value,
            current_tc[
                "fixture_context"
            ],
            now_certainty,
            now_history,
            curve_evidence_for(
                "TC",
                planning_gameweek,
            ),
        )

        later_certainty = (
            _fixture_certainty(
                planning_gameweek,
                best_later_tc[
                    "gameweek"
                ],
            )
            if best_later_tc
            else None
        )
        later_history = (
            _historical_evidence(
                "TC",
                best_later_tc[
                    "gameweek"
                ],
                bootstrap,
                fixtures,
            )
            if best_later_tc
            else None
        )
        later_decision = (
            _chip_recommendation(
                "TC",
                later_value,
                best_later_tc[
                    "fixture_context"
                ],
                later_certainty,
                later_history,
            )
            if best_later_tc
            else None
        )

        rows.append({
            "chip": "Triple Captain",
            "short": "TC",
            "now_value":
                now_value,
            "now_context":
                (
                    f"{current_tc['best_candidate']['name']} · "
                    f"{current_tc['fixture_context']['label']}"
                ),
            "best_later_fixture_context":
                (
                    best_later_tc[
                        "fixture_context"
                    ]["label"]
                    if best_later_tc
                    else None
                ),
            "best_later_value":
                later_value,
            "best_later_gw":
                (
                    best_later_tc[
                        "gameweek"
                    ]
                    if best_later_tc
                    else None
                ),
            "cost_of_waiting":
                (
                    now_value
                    - later_value
                    if later_value
                    is not None
                    else None
                ),
            "status":
                "comparable",
            "recommendation":
                decision["recommendation"],
            "recommendation_reason":
                decision["reason"],
            "fixture_certainty":
                now_certainty["level"],
            "fixture_certainty_reason":
                now_certainty["reason"],
            "model_confidence":
                decision["model_confidence"],
            "historical":
                now_history,
            "best_later_fixture_certainty":
                (
                    later_certainty["level"]
                    if later_certainty
                    else None
                ),
            "best_later_historical":
                later_history,
            "best_later_recommendation":
                (
                    later_decision[
                        "recommendation"
                    ]
                    if later_decision
                    else None
                ),
            "best_later_model_confidence":
                (
                    later_decision[
                        "model_confidence"
                    ]
                    if later_decision
                    else None
                ),
            "best_later_recommendation_reason":
                (
                    later_decision[
                        "reason"
                    ]
                    if later_decision
                    else None
                ),
        })

    add_timing_row(
        "Wildcard",
        "WC",
        "wc_value",
        "unrestricted vs hold",
    )

    add_timing_row(
        "Free Hit",
        "FH",
        "fh_value",
        "one-week optimal vs hold",
    )

    return {
        "gameweek":
            planning_gameweek,
        "rows":
            rows,
        "curves":
            curves,
        "note":
            (
                "Timing windows hold today's squad, "
                "selling values and bank constant. "
                "Future fixture assignments use the "
                "current FPL schedule and may change "
                "if matches are rearranged. They are "
                "opportunity snapshots, not forecasts "
                "of future transfers."
            ),
    }


def build_chip_planner(
    include_opportunity=False,
    force_refresh=False,
):
    planning_gameweek = (
        get_planning_gameweek()
    )

    current_team = get_my_team()

    chip_horizon_end = (
        _chip_horizon_end(
            planning_gameweek
        )
    )

    cache_key = _chip_cache_key(
        planning_gameweek,
        current_team,
    )

    cache_namespace = (
        "chip_planner_with_opportunity"
        if include_opportunity
        else "chip_planner"
    )

    if not force_refresh:
        cached = get_cached_result(
            cache_namespace,
            cache_key,
            CHIP_CACHE_MODEL_VERSION,
        )

        if cached is not None:
            cached["cache"] = {
                "hit": True,
                "namespace":
                    cache_namespace,
            }
            return cached

    players = load_players(
        projection_end_gameweek=
            chip_horizon_end,
        long_range_regression=True,
    )

    players_by_id = {
        player["id"]: player
        for player in players
    }

    bench = []

    for pick in sorted(
        current_team.get(
            "picks",
            [],
        ),
        key=lambda p:
            p.get(
                "position",
                99,
            ),
    ):
        if pick.get(
            "position",
            99,
        ) <= 11:
            continue

        player = players_by_id.get(
            pick["element"],
            {},
        )

        bench.append({
            "id":
                pick["element"],
            "name":
                player.get(
                    "name",
                    str(
                        pick["element"]
                    ),
                ),
            "position":
                player.get(
                    "position",
                    "",
                ),
            "projection":
                _projection(
                    player,
                    planning_gameweek,
                ),
            "status":
                player.get(
                    "status",
                    "",
                ),
        })

    bench_projection = sum(
        player["projection"]
        for player in bench
    )

    normal_scenarios = (
        _normal_scenarios(
            players,
            current_team,
            planning_gameweek,
        )
    )

    bench_boost = (
        _bench_boost_scenarios(
            players,
            current_team,
            planning_gameweek,
            normal_scenarios=
                normal_scenarios,
        )
    )

    triple_captain = (
        _triple_captain_windows(
            players,
            current_team,
            planning_gameweek,
            chip_horizon_end,
        )
    )

    wildcard = (
        _wildcard_analysis(
            players,
            current_team,
            planning_gameweek,
            normal_scenarios=
                normal_scenarios,
        )
    )

    free_hit = (
        _free_hit_analysis(
            players,
            current_team,
            planning_gameweek,
            normal_scenarios=
                normal_scenarios,
        )
    )

    opportunity = None

    if include_opportunity:
        timing_windows = (
            _future_chip_windows(
                players,
                current_team,
                planning_gameweek,
                chip_horizon_end,
                force_refresh=force_refresh,
            )
        )

        opportunity = (
            _chip_opportunity_summary(
                planning_gameweek,
                bench_boost,
                triple_captain,
                wildcard,
                free_hit,
                timing_windows,
                bootstrap=get_bootstrap(),
                fixtures=get_fixtures(),
            )
        )

    cards = _chip_cards(
        current_team,
        planning_gameweek=
            planning_gameweek,
    )

    by_name = {}

    for card in cards:
        by_name.setdefault(
            card["name"],
            [],
        ).append(card)

    display_cards = []

    for name in [
        "bboost",
        "3xc",
        "wildcard",
        "freehit",
    ]:
        matching = by_name.get(
            name,
            [],
        )

        if matching:
            display_cards.extend(
                matching
            )
        else:
            meta = CHIP_META[name]
            display_cards.append({
                "name": name,
                "title":
                    meta["title"],
                "short":
                    meta["short"],
                "status":
                    "unknown",
                "number":
                    None,
                "start_event":
                    None,
                "stop_event":
                    None,
                "played_event":
                    None,
                "raw":
                    {},
            })

    for card in display_cards:

        if card["name"] == "bboost":
            best = bench_boost[
                "best_practical"
            ]

            if best is None:
                card["evaluation"] = (
                    "Bench Boost scenarios "
                    "could not be scored."
                )
                card["note"] = (
                    "No valid optimiser "
                    "scenario was returned."
                )
            else:
                card["evaluation"] = (
                    f"Current bench adds "
                    f"{bench_projection:.1f} pts. "
                    f"Best practical BB setup "
                    f"projects "
                    f"{best['net_projection']:.1f} "
                    f"net GW points, with "
                    f"{best['bb_uplift']:.1f} pts "
                    f"of BB uplift."
                )
                card["note"] = (
                    "Practical ranking compares "
                    "the Bench Boost plan against "
                    "the equivalent normal plan, "
                    "including a smaller value for "
                    "the four following Gameweeks."
                )

        elif card["name"] == "3xc":
            best = triple_captain[
                "best"
            ]

            if best is None:
                card["evaluation"] = (
                    "Triple Captain windows "
                    "could not be scored."
                )
                card["note"] = (
                    "No valid captain projection "
                    "was returned."
                )
            else:
                candidate = best[
                    "best_candidate"
                ]

                ownership_text = (
                    "already owned"
                    if best[
                        "best_is_owned"
                    ]
                    else "not currently owned"
                )

                card["evaluation"] = (
                    f"Best projected window through "
                    f"GW{chip_horizon_end} is GW"
                    f"{best['gameweek']}: "
                    f"{candidate['name']} at "
                    f"{best['best_tc_uplift']:.1f} "
                    f"pts of TC uplift "
                    f"({ownership_text})."
                )
                card["note"] = (
                    "The model compares every "
                    "remaining Gameweek in the "
                    "current chip half. It shows "
                    "both the best "
                    "captain already in the squad "
                    "and the best projected "
                    "league-wide candidate."
                )

        elif card["name"] == "wildcard":
            card["evaluation"] = (
                f"Unrestricted optimal squad "
                f"changes {wildcard['changes']} "
                f"players and beats the best "
                f"tested normal plan by "
                f"{wildcard['objective_uplift']:.1f} "
                f"model pts."
            )
            card["note"] = (
                f"Best normal plan uses "
                f"{wildcard['normal_transfers']} "
                f"transfer"
                f"{'s' if wildcard['normal_transfers'] != 1 else ''} "
                f"with a "
                f"{wildcard['normal_hit']}-pt hit. "
                f"Immediate GW"
                f"{planning_gameweek} advantage is "
                f"{wildcard['gw_uplift']:.1f} pts. "
                f"Wildcard budget uses your real "
                f"selling value plus bank: "
                f"£{wildcard['budget'] / 10:.1f}m."
            )

        elif card["name"] == "freehit":
            normal = free_hit[
                "normal"
            ]

            if normal is None:
                card["evaluation"] = (
                    "Free Hit opportunity could "
                    "not be scored."
                )
                card["note"] = (
                    "No valid normal comparison "
                    "plan was returned."
                )
            else:
                card["evaluation"] = (
                    f"Best one-week Free Hit "
                    f"squad projects "
                    f"{free_hit['free_hit_gw']:.1f} "
                    f"pts, an uplift of "
                    f"{free_hit['uplift']:.1f} pts "
                    f"over the best tested normal "
                    f"plan."
                )
                card["note"] = (
                    f"The comparison normal plan "
                    f"uses {normal['transfers']} "
                    f"transfer"
                    f"{'s' if normal['transfers'] != 1 else ''} "
                    f"and a {normal['hit_cost']}-pt "
                    f"hit. The Free Hit squad then "
                    f"reverts automatically next "
                    f"Gameweek."
                )

    result = {
        "gameweek":
            planning_gameweek,
        "chip_horizon_end":
            chip_horizon_end,
        "chips":
            display_cards,
        "bench":
            bench,
        "bench_projection":
            bench_projection,
        "bench_boost":
            bench_boost,
        "triple_captain":
            triple_captain,
        "wildcard":
            wildcard,
        "free_hit":
            free_hit,
        "fixture_context":
            _fixture_context(
                players,
                planning_gameweek,
            ),
        "opportunity":
            opportunity,
        "cache": {
            "hit": False,
            "namespace":
                cache_namespace,
        },
    }

    save_cached_result(
        cache_namespace,
        cache_key,
        CHIP_CACHE_MODEL_VERSION,
        result,
        CHIP_PLANNER_CACHE_TTL,
    )

    return result



def build_chip_opportunity(
    force_refresh=False,
):
    planning_gameweek = (
        get_planning_gameweek()
    )

    current_team = get_my_team()

    chip_horizon_end = (
        _chip_horizon_end(
            planning_gameweek
        )
    )

    cache_key = _chip_cache_key(
        planning_gameweek,
        current_team,
    )

    if not force_refresh:
        cached = get_cached_result(
            "chip_opportunity",
            cache_key,
            CHIP_CACHE_MODEL_VERSION,
        )

        if cached is not None:
            cached["cache"] = {
                "hit": True,
                "namespace":
                    "chip_opportunity",
            }
            return cached

    players = load_players(
        projection_end_gameweek=
            chip_horizon_end,
        long_range_regression=True,
    )

    triple_captain = (
        _triple_captain_windows(
            players,
            current_team,
            planning_gameweek,
            chip_horizon_end,
        )
    )

    timing_windows = (
        _future_chip_windows(
            players,
            current_team,
            planning_gameweek,
            chip_horizon_end,
            force_refresh=force_refresh,
        )
    )

    opportunity = (
        _chip_opportunity_summary(
            planning_gameweek,
            None,
            triple_captain,
            None,
            None,
            timing_windows,
            bootstrap=get_bootstrap(),
            fixtures=get_fixtures(),
        )
    )

    opportunity["cache"] = {
        "hit": False,
        "namespace":
            "chip_opportunity",
    }

    save_cached_result(
        "chip_opportunity",
        cache_key,
        CHIP_CACHE_MODEL_VERSION,
        opportunity,
        CHIP_OPPORTUNITY_CACHE_TTL,
    )

    return opportunity
