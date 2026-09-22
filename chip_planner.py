from fpl_api import (
    get_my_team,
    get_planning_gameweek,
)

from optimizer import load_players

from transfer_optimizer import (
    optimise_transfers,
)


POST_BB_HORIZON_WEIGHT = 0.15


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

        if result is None:
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

        gross_projection = (
            squad_projection
            + captain_projection
        )

        net_projection = (
            gross_projection
            - result["hit_cost"]
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
            "formation":
                _formation(
                    starters
                ),
            "post_bb_projection":
                post_bb_projection,
            "pairs":
                _pair_transfers(
                    result
                ),
        })

    if not scenarios:
        return {
            "scenarios": [],
            "baseline": None,
            "best": None,
            "best_practical": None,
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

        scenario["practical_gain"] = (
            scenario["gain_vs_current"]
            +
            (
                scenario["post_bb_delta"]
                * POST_BB_HORIZON_WEIGHT
            )
        )

        scenario["practical_score"] = (
            scenario["net_projection"]
            +
            (
                scenario["post_bb_projection"]
                * POST_BB_HORIZON_WEIGHT
            )
        )

        scenario["rental_risk"] = (
            scenario["gain_vs_current"] > 0
            and
            scenario["post_bb_delta"] < 0
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
        "best_no_hit":
            best_no_hit,
    }


def build_chip_planner():
    planning_gameweek = (
        get_planning_gameweek()
    )

    current_team = get_my_team()
    players = load_players()

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
                    f"net GW points."
                )
                card["note"] = (
                    "Practical ranking includes "
                    "this Gameweek, transfer hits "
                    "and a smaller value for the "
                    "four following Gameweeks."
                )

        elif card["name"] == "3xc":
            card["evaluation"] = (
                "Captain opportunity model "
                "not scored yet."
            )
            card["note"] = (
                "Will compare the extra captain "
                "multiplier against future "
                "premium-captain opportunities."
            )

        elif card["name"] == "wildcard":
            card["evaluation"] = (
                "Wildcard opportunity model "
                "not scored yet."
            )
            card["note"] = (
                "Will compare the current squad "
                "with an unrestricted optimal "
                "squad over a multi-Gameweek "
                "horizon."
            )

        elif card["name"] == "freehit":
            card["evaluation"] = (
                "Free Hit opportunity model "
                "not scored yet."
            )
            card["note"] = (
                "Will compare the current XI "
                "with the best legal one-week "
                "squad."
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
    }
