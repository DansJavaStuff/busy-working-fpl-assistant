from fpl_api import (
    get_my_team,
    get_planning_gameweek,
)

from optimizer import (
    load_players,
    optimise_squad,
    calculate_objective_score,
)

from transfer_optimizer import (
    optimise_transfers,
)


POST_BB_HORIZON_WEIGHT = 0.15
FIRST_HALF_END_GW = 19


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


def _projection(player, gameweek):
    return float(
        player.get(
            f"proj_gw{gameweek}",
            0.0,
        )
        or 0.0
    )


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


def _chip_cards(current_team):
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


def _best_normal_scenario(
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


def build_chip_planner():
    planning_gameweek = (
        get_planning_gameweek()
    )

    current_team = get_my_team()
    players = load_players(
        projection_end_gameweek=
            FIRST_HALF_END_GW,
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

    bench_boost = (
        _bench_boost_scenarios(
            players,
            current_team,
            planning_gameweek,
        )
    )

    triple_captain = (
        _triple_captain_windows(
            players,
            current_team,
            planning_gameweek,
            FIRST_HALF_END_GW,
        )
    )

    wildcard = (
        _wildcard_analysis(
            players,
            current_team,
            planning_gameweek,
        )
    )

    free_hit = (
        _free_hit_analysis(
            players,
            current_team,
            planning_gameweek,
        )
    )

    cards = _chip_cards(
        current_team
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
                    f"Best projected first-half "
                    f"window is GW"
                    f"{best['gameweek']}: "
                    f"{candidate['name']} at "
                    f"{best['best_tc_uplift']:.1f} "
                    f"pts of TC uplift "
                    f"({ownership_text})."
                )
                card["note"] = (
                    "The model now compares every "
                    "remaining Gameweek through "
                    "GW19. It shows both the best "
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

    return {
        "gameweek":
            planning_gameweek,
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
    }
