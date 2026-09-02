import pulp

from fpl_api import (
    get_my_team,
    get_planning_gameweek,
)

from optimizer import (load_players,calculate_captain_score,)

import csv
from pathlib import Path

CBC_PATH = "/usr/bin/cbc"
MINIMUM_FREE_TRANSFER_GAIN = 1.0

#
# Same idea as the existing squad optimiser:
# current GW matters most, but retain some
# value for the following fixtures.
#
HORIZON_WEIGHT = 0.15

def save_season_history(
    gameweek,
    current_score,
    best_transfer_score,
    recommended_transfers,
    hit_cost,
    bank_before,
    bank_after,
    free_transfers,
):
    history_file = Path(
        "data/season_history.csv"
    )

    history_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    #
    # Keep ideal_score and gap_to_ideal
    # for compatibility with the GW2/GW3
    # history already recorded.
    #
    fieldnames = [
        "gameweek",
        "current_score",
        "best_transfer_score",
        "recommended_transfers",
        "hit_cost",
        "bank_before",
        "bank_after",
        "free_transfers",
        "ideal_score",
        "gap_to_ideal",
    ]

    rows = []

    if history_file.exists():

        with history_file.open(
            "r",
            newline=""
        ) as f:

            rows = list(
                csv.DictReader(f)
            )

    #
    # Only one pre-deadline snapshot per GW.
    #
    rows = [
        row
        for row in rows
        if int(row["gameweek"]) != gameweek
    ]

    rows.append(
        {
            "gameweek": gameweek,
            "current_score":
                f"{current_score:.2f}",
            "best_transfer_score":
                f"{best_transfer_score:.2f}",
            "recommended_transfers":
                recommended_transfers,
            "hit_cost":
                hit_cost,
            "bank_before":
                bank_before,
            "bank_after":
                bank_after,
            "free_transfers":
                free_transfers,
            "ideal_score": "",
            "gap_to_ideal": "",
        }
    )

    rows.sort(
        key=lambda row:
            int(row["gameweek"])
    )

    with history_file.open(
        "w",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

def get_projection(player, gameweek):
    return player.get(
        f"proj_gw{gameweek}",
        0.0
    )

def get_horizon_projection(
    player,
    planning_gameweek
):
    """
    Return the rolling multi-gameweek projection
    already calculated by optimizer.py.

    proj_5gw moves forward with the planning
    gameweek, so this does not stop working
    after GW5.
    """

    return player.get(
        "proj_5gw",
        0.0
    )

def optimise_transfers(
    players,
    current_team,
    planning_gameweek,
    number_of_transfers,
):

    picks = current_team["picks"]
    transfer_state = current_team[
        "transfers"
    ]

    current_ids = {
        pick["element"]
        for pick in picks
    }

    selling_prices = {
        pick["element"]:
            pick["selling_price"]
        for pick in picks
    }

    players_by_id = {
        p["id"]: p
        for p in players
    }

    #
    # Make sure every player we currently own
    # exists in the projection pool.
    #
    missing = (
        current_ids
        - set(players_by_id)
    )

    if missing:
        raise RuntimeError(
            "Current squad contains players "
            f"missing from projection data: {missing}"
        )

    problem = pulp.LpProblem(
        f"GW{planning_gameweek}_"
        f"{number_of_transfers}_transfers",
        pulp.LpMaximize
    )

    selected = {
        p["id"]: pulp.LpVariable(
            f"selected_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    starter = {
        p["id"]: pulp.LpVariable(
            f"starter_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    captain = {
        p["id"]: pulp.LpVariable(
            f"captain_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    #
    # OBJECTIVE
    #
    # Starting XI gets GW2 projected points.
    # Captain adds another copy.
    # Whole squad gets a smaller future-horizon
    # contribution.
    #
    problem += pulp.lpSum(
        (
            starter[p["id"]]
            * get_projection(
                p,
                planning_gameweek
            )
        )
        +
        (
            captain[p["id"]]
            * calculate_captain_score(p)
        )
        +
        (
            selected[p["id"]]
            * get_horizon_projection(
                p,
                planning_gameweek
            )
            * HORIZON_WEIGHT
        )
        for p in players
    )

    #
    # 15-player squad
    #
    problem += pulp.lpSum(
        selected[p["id"]]
        for p in players
    ) == 15

    #
    # Exactly N transfers IN.
    #
    problem += pulp.lpSum(
        selected[p["id"]]
        for p in players
        if p["id"] not in current_ids
    ) == number_of_transfers

    #
    # Exactly N transfers OUT.
    #
    problem += pulp.lpSum(
        1 - selected[player_id]
        for player_id in current_ids
    ) == number_of_transfers

    #
    # Transfer budget.
    #
    # Important:
    #
    # We only pay CURRENT PRICE for players
    # we buy.
    #
    # We receive actual SELLING PRICE for
    # players we sell.
    #
    # Retained players don't need to be
    # re-purchased at their current value.
    #
    incoming_cost = pulp.lpSum(
        selected[p["id"]]
        * p["cost"]
        for p in players
        if p["id"] not in current_ids
    )

    outgoing_value = pulp.lpSum(
        (
            1 - selected[player_id]
        )
        * selling_prices[player_id]
        for player_id in current_ids
    )

    problem += (
        incoming_cost
        <=
        outgoing_value
        + transfer_state["bank"]
    )

    #
    # Squad positions
    #
    position_requirements = {
        "GKP": 2,
        "DEF": 5,
        "MID": 5,
        "FWD": 3,
    }

    for position, required in (
        position_requirements.items()
    ):

        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["position"] == position
        ) == required

    #
    # Maximum three from one club
    #
    team_ids = {
        p["team_id"]
        for p in players
    }

    for team_id in team_ids:

        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["team_id"] == team_id
        ) <= 3

    #
    # STARTING XI
    #
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
    ) == 11

    for p in players:

        problem += (
            starter[p["id"]]
            <= selected[p["id"]]
        )

    #
    # One goalkeeper
    #
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "GKP"
    ) == 1

    #
    # Valid FPL formation
    #
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "DEF"
    ) >= 3

    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "DEF"
    ) <= 5

    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "MID"
    ) >= 2

    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "MID"
    ) <= 5

    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "FWD"
    ) >= 1

    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "FWD"
    ) <= 3

    #
    # CAPTAIN
    #
    problem += pulp.lpSum(
        captain[p["id"]]
        for p in players
    ) == 1

    for p in players:

        problem += (
            captain[p["id"]]
            <= starter[p["id"]]
        )

    problem.solve(
        pulp.COIN_CMD(
            path=CBC_PATH,
            msg=False
        )
    )

    if (
        pulp.LpStatus[problem.status]
        != "Optimal"
    ):
        return None

    squad = []

    for p in players:

        if selected[p["id"]].value() == 1:

            item = p.copy()

            item["starter"] = (
                starter[p["id"]].value()
                == 1
            )

            item["captain"] = (
                captain[p["id"]].value()
                == 1
            )

            squad.append(item)

    incoming = [
        p
        for p in squad
        if p["id"] not in current_ids
    ]

    selected_ids = {
        p["id"]
        for p in squad
    }

    outgoing = [
        players_by_id[player_id]
        for player_id in current_ids
        if player_id not in selected_ids
    ]

    #
    # Actual money after transfers
    #
    money_available = (
        transfer_state["bank"]
        +
        sum(
            selling_prices[p["id"]]
            for p in outgoing
        )
    )

    money_spent = sum(
        p["cost"]
        for p in incoming
    )

    bank_after = (
        money_available
        - money_spent
    )

    #
    # Remaining free transfers.
    #
    free_transfers = max(
        0,
        transfer_state["limit"]
        - transfer_state["made"]
    )

    paid_transfers = max(
        0,
        number_of_transfers
        - free_transfers
    )

    hit_cost = (
        paid_transfers
        * transfer_state["cost"]
    )

    raw_score = pulp.value(
        problem.objective
    )

    net_score = (
        raw_score
        - hit_cost
    )

    #
    # Choose VC from the best projected
    # starter other than captain.
    #
    vice_candidates = [
        p
        for p in squad
        if p["starter"]
        and not p["captain"]
    ]

    vice_captain = max(
        vice_candidates,
        key=calculate_captain_score,
    )

    return {
        "transfers": number_of_transfers,
        "incoming": incoming,
        "outgoing": outgoing,
        "squad": squad,
        "bank_after": bank_after,
        "hit_cost": hit_cost,
        "raw_score": raw_score,
        "net_score": net_score,
        "vice_captain": vice_captain,
    }


def print_scenario(
    result,
    planning_gameweek
):

    print()
    print("=" * 92)

    if result["transfers"] == 0:

        print("HOLD - NO TRANSFERS")

    else:

        print(
            f"{result['transfers']} "
            f"TRANSFER"
            f"{'S' if result['transfers'] != 1 else ''}"
        )

    print("=" * 92)

    if result["transfers"]:

        print()
        print("OUT")
        print("-" * 50)

        for p in result["outgoing"]:

            print(
                f"{p['name']:18} "
                f"{p['team']:18} "
                f"{p['position']:3} "
                f"£{p['price']:4.1f}m "
                f"GW{planning_gameweek} "
                f"{get_projection(p, planning_gameweek):.2f} "
                f"5GW {p['proj_5gw']:.2f} "
            )

        print()
        print("IN")
        print("-" * 50)

        for p in result["incoming"]:

            print(
                f"{p['name']:18} "
                f"{p['team']:18} "
                f"{p['position']:3} "
                f"£{p['price']:4.1f}m "
                f"GW{planning_gameweek} "
                f"{get_projection(p, planning_gameweek):.2f} "
                f"5GW {p['proj_5gw']:.2f} "
            )

    starters = [
        p
        for p in result["squad"]
        if p["starter"]
    ]

    starters.sort(
        key=lambda p: (
            p["position_id"],
            -get_projection(
                p,
                planning_gameweek
            )
        )
    )

    print()
    print("STARTING XI")
    print("-" * 92)

    for p in starters:

        captain = (
            " (C)"
            if p["captain"]
            else ""
        )

        vice = (
            " (VC)"
            if (
                p["id"]
                ==
                result[
                    "vice_captain"
                ]["id"]
            )
            else ""
        )

        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"{p['position']:3} "
            f"GW{planning_gameweek} "
            f"{get_projection(p, planning_gameweek):5.2f}"
            f"{captain}{vice}"
        )

    bench = [
        p
        for p in result["squad"]
        if not p["starter"]
    ]

    backup_gk = [
        p
        for p in bench
        if p["position"] == "GKP"
    ]

    outfield_bench = [
        p
        for p in bench
        if p["position"] != "GKP"
    ]

    outfield_bench.sort(
        key=lambda p:
            get_projection(
                p,
                planning_gameweek
            ),
        reverse=True
    )

    print()
    print("BENCH")
    print("-" * 92)

    bench_number = 1

    for p in outfield_bench:

        print(
            f"{bench_number}. "
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"{p['position']:3} "
            f"{get_projection(p, planning_gameweek):5.2f}"
        )

        bench_number += 1

    for p in backup_gk:

        print(
            f"GK  "
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"{get_projection(p, planning_gameweek):5.2f}"
        )

    captain_player = next(
        p
        for p in result["squad"]
        if p["captain"]
    )

    print()
    print(
        f"Captain: "
        f"{captain_player['name']}"
    )

    print(
        f"Vice: "
        f"{result['vice_captain']['name']}"
    )

    print(
        f"Bank after: "
        f"£{result['bank_after'] / 10:.1f}m"
    )

    print(
        f"Hit cost: "
        f"-{result['hit_cost']} pts"
    )

    print(
        f"Model score: "
        f"{result['raw_score']:.2f}"
    )

    print(
        f"Net score: "
        f"{result['net_score']:.2f}"
    )


if __name__ == "__main__":

    print(
        "Downloading live FPL data..."
    )

    planning_gameweek = (
        get_planning_gameweek()
    )

    current_team = get_my_team()

    players = load_players()

    transfers = current_team[
        "transfers"
    ]

    print()
    print(
        f"PLANNING FOR GW"
        f"{planning_gameweek}"
    )

    print(
        f"Bank: "
        f"£{transfers['bank'] / 10:.1f}m"
    )

    print(
        f"Free transfers: "
        f"{max(0, transfers['limit'] - transfers['made'])}"
    )

    print(
        f"Additional transfer cost: "
        f"{transfers['cost']} points"
    )

    results = []

    for number_of_transfers in range(
        0,
        4
    ):

        result = optimise_transfers(
            players,
            current_team,
            planning_gameweek,
            number_of_transfers,
        )

        if result:
            results.append(result)

    for result in results:

        print_scenario(
            result,
            planning_gameweek
        )

    best = max(
        results,
        key=lambda r:
            r["net_score"]
    )

    hold = next(
        r
        for r in results
        if r["transfers"] == 0
    )

    transfer_gain = (
        best["net_score"]
        - hold["net_score"]
    )

    roll_transfer = (
        best["transfers"] == 0
        or transfer_gain
        < MINIMUM_FREE_TRANSFER_GAIN
    )

    print()
    print("=" * 92)
    print("RECOMMENDATION")
    print("=" * 92)

    if roll_transfer:

        print(
            "ROLL THE TRANSFER."
        )

        if best["transfers"] > 0:

            print()
            print(
                f"Best available transfer gains "
                f"{transfer_gain:+.2f} points, "
                f"below the "
                f"{MINIMUM_FREE_TRANSFER_GAIN:.2f} "
                f"threshold."
            )

            print()

            print("Best optional move:")

            for outgoing in sorted(
                best["outgoing"],
                key=lambda p: p["position_id"],
            ):

                incoming = next(
                    p
                    for p in best["incoming"]
                    if p["position"] == outgoing["position"]
                )

                print(
                    f"{outgoing['name']} "
                    f"-> "
                    f"{incoming['name']}"
                )

    else:

        print(
            f"MAKE "
            f"{best['transfers']} "
            f"TRANSFER"
            f"{'S' if best['transfers'] != 1 else ''}."
        )

        for outgoing in sorted(
            best["outgoing"],
            key=lambda p: p["position_id"],
        ):

            incoming = next(
                p
                for p in best["incoming"]
                if p["position"] == outgoing["position"]
            )

            print(
                f"{outgoing['name']} "
                f"-> "
                f"{incoming['name']}"
            )

        if best["hit_cost"]:

            print(
                f"Points hit: "
                f"-{best['hit_cost']}"
            )

    #
    # The mathematically best transfer path is
    # not necessarily the recommended action.
    #
    # If the gain is below our threshold, HOLD
    # is the actual recommendation.
    #
    recommended = (
        hold
        if roll_transfer
        else best
    )

    free_transfers = max(
        0,
        transfers["limit"]
        - transfers["made"]
    )

    print()
    print("=" * 92)
    print(
        f"GW{planning_gameweek} "
        "WEEKLY SUMMARY"
    )
    print("=" * 92)

    print(
        f"Current squad model score : "
        f"{hold['net_score']:.2f}"
    )

    print(
        f"Best available path       : "
        f"{best['net_score']:.2f}"
    )

    print(
        f"Best path gain            : "
        f"{transfer_gain:+.2f}"
    )

    if roll_transfer:

        print(
            "Recommended action        : "
            "ROLL"
        )

    else:

        print(
            f"Recommended action        : "
            f"{recommended['transfers']} "
            f"TRANSFER"
            f"{'S' if recommended['transfers'] != 1 else ''}"
        )

    print(
        f"Bank now                  : "
        f"£{transfers['bank'] / 10:.1f}m"
    )

    print(
        f"Bank after recommendation : "
        f"£{recommended['bank_after'] / 10:.1f}m"
    )

    print(
        f"Free transfers available  : "
        f"{free_transfers}"
    )

    if recommended["hit_cost"]:

        print(
            f"Transfer hit              : "
            f"-{recommended['hit_cost']} pts"
        )

    save_season_history(
        gameweek=planning_gameweek,
        current_score=hold["net_score"],
        best_transfer_score=best["net_score"],
        recommended_transfers=
            recommended["transfers"],
        hit_cost=
            recommended["hit_cost"],
        bank_before=
            transfers["bank"],
        bank_after=
            recommended["bank_after"],
        free_transfers=
            free_transfers,
    )

    print()
    print(
        "Weekly snapshot saved to "
        "data/season_history.csv"
    )

