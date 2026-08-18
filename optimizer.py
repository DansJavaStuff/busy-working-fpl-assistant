from collections import defaultdict

import pulp

from fpl_api import get_bootstrap


BUDGET = 1000  # FPL stores prices in tenths: £100.0m = 1000


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def load_players():
    data = get_bootstrap()

    teams = {
        team["id"]: team["name"]
        for team in data["teams"]
    }

    positions = {
        position["id"]: position["singular_name_short"]
        for position in data["element_types"]
    }

    players = []

    for p in data["elements"]:

        # Ignore players FPL says cannot currently be selected
        if not p.get("can_select", True):
            continue

        # A very simple first-pass GW1 rating.
        #
        # ep_next gets most of the weight because it is FPL's current
        # next-gameweek estimate.
        #
        # Last-season points and minutes provide some history/reliability.

        ep_next = safe_float(p.get("ep_next"))
        total_points = safe_float(p.get("total_points"))
        minutes = safe_float(p.get("minutes"))
        starts = safe_float(p.get("starts"))
        ownership = safe_float(p.get("selected_by_percent"))

        season_points_per_game = safe_float(p.get("points_per_game"))

        # Minutes reliability:
        # 3420 = 38 full matches
        minutes_factor = min(minutes / 3420, 1.0)

        # Initial rating.
        rating = (
            ep_next * 10.0
            + season_points_per_game * 2.0
            + minutes_factor * 3.0
        )

        # Small availability penalty
        status = p.get("status", "a")

        if status != "a":
            rating *= 0.5

        chance = p.get("chance_of_playing_next_round")

        if chance is not None:
            rating *= safe_float(chance) / 100.0

        players.append({
            "id": p["id"],
            "name": p["web_name"],
            "team_id": p["team"],
            "team": teams[p["team"]],
            "position": positions[p["element_type"]],
            "position_id": p["element_type"],
            "cost": p["now_cost"],
            "price": p["now_cost"] / 10,
            "ep_next": ep_next,
            "points_per_game": season_points_per_game,
            "total_points": total_points,
            "minutes": int(minutes),
            "starts": int(starts),
            "ownership": ownership,
            "status": status,
            "rating": rating,
        })

    return players


def optimise_squad(players):

    problem = pulp.LpProblem(
        "FPL_GW1_Squad",
        pulp.LpMaximize
    )

    selected = {
        p["id"]: pulp.LpVariable(
            f"player_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    # Maximise our player rating
    problem += pulp.lpSum(
        selected[p["id"]] * p["rating"]
        for p in players
    )

    # Exactly 15 players
    problem += pulp.lpSum(
        selected[p["id"]]
        for p in players
    ) == 15

    # Budget
    problem += pulp.lpSum(
        selected[p["id"]] * p["cost"]
        for p in players
    ) <= BUDGET

    # Position requirements
    position_limits = {
        "GKP": 2,
        "DEF": 5,
        "MID": 5,
        "FWD": 3,
    }

    for position, required in position_limits.items():
        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["position"] == position
        ) == required

    # Maximum 3 players from any Premier League club
    teams = set(
        p["team_id"]
        for p in players
    )

    for team_id in teams:
        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["team_id"] == team_id
        ) <= 3

    problem.solve(
        pulp.COIN_CMD(
            path="/usr/bin/cbc",
            msg=False
        )
    )

    if pulp.LpStatus[problem.status] != "Optimal":
        raise RuntimeError(
            f"Optimisation failed: {pulp.LpStatus[problem.status]}"
        )

    squad = [
        p
        for p in players
        if selected[p["id"]].value() == 1
    ]

    return squad


def print_squad(squad):

    position_order = {
        "GKP": 1,
        "DEF": 2,
        "MID": 3,
        "FWD": 4,
    }

    squad.sort(
        key=lambda p: (
            position_order[p["position"]],
            -p["rating"]
        )
    )

    total_cost = sum(p["cost"] for p in squad)

    print()
    print("=" * 84)
    print("                     FPL GW1 OPTIMISED SQUAD")
    print("=" * 84)

    current_position = None

    for p in squad:

        if p["position"] != current_position:
            current_position = p["position"]

            names = {
                "GKP": "GOALKEEPERS",
                "DEF": "DEFENDERS",
                "MID": "MIDFIELDERS",
                "FWD": "FORWARDS",
            }

            print()
            print(names[current_position])
            print("-" * 84)

        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"£{p['price']:4.1f}m   "
            f"EP {p['ep_next']:4.1f}   "
            f"PPG {p['points_per_game']:4.1f}   "
            f"Owned {p['ownership']:5.1f}%   "
            f"Score {p['rating']:5.1f}"
        )

    print()
    print("=" * 84)
    print(f"Squad cost : £{total_cost / 10:.1f}m")
    print(f"In bank    : £{(BUDGET - total_cost) / 10:.1f}m")
    print("=" * 84)


if __name__ == "__main__":

    print("Downloading live FPL data...")

    players = load_players()

    print(f"Considering {len(players)} selectable players...")

    squad = optimise_squad(players)

    print_squad(squad)
