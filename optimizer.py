from collections import defaultdict

import pulp

from fpl_api import get_bootstrap, get_fixtures

BUDGET = 1000  # FPL stores prices in tenths: £100.0m = 1000


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def build_fixture_scores():

    fixtures = get_fixtures()

    # Earlier gameweeks matter more
    gw_weights = {
        1: 1.00,
        2: 0.90,
        3: 0.80,
        4: 0.70,
        5: 0.60,
    }

    #
    # Convert FPL difficulty into a positive score:
    #
    # Difficulty 1 -> 5 points
    # Difficulty 2 -> 4
    # Difficulty 3 -> 3
    # Difficulty 4 -> 2
    # Difficulty 5 -> 1
    #
    difficulty_score = {
        1: 5.0,
        2: 4.0,
        3: 3.0,
        4: 2.0,
        5: 1.0,
    }

    fixture_scores = {}
    fixture_details = {}

    for fixture in fixtures:

        gw = fixture.get("event")

        if gw not in gw_weights:
            continue

        home_team = fixture["team_h"]
        away_team = fixture["team_a"]

        home_difficulty = fixture["team_h_difficulty"]
        away_difficulty = fixture["team_a_difficulty"]

        weight = gw_weights[gw]

        home_score = (
            difficulty_score[home_difficulty]
            * weight
        )

        away_score = (
            difficulty_score[away_difficulty]
            * weight
        )

        fixture_scores[home_team] = (
            fixture_scores.get(home_team, 0)
            + home_score
        )

        fixture_scores[away_team] = (
            fixture_scores.get(away_team, 0)
            + away_score
        )

        fixture_details.setdefault(
            home_team,
            []
        ).append({
            "gw": gw,
            "difficulty": home_difficulty,
            "home": True,
            "opponent": away_team,
        })

        fixture_details.setdefault(
            away_team,
            []
        ).append({
            "gw": gw,
            "difficulty": away_difficulty,
            "home": False,
            "opponent": home_team,
        })

    return fixture_scores, fixture_details

def load_players():
    data = get_bootstrap()

    fixture_scores, fixture_details = build_fixture_scores()
   
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

        xg90 = safe_float(
            p.get("expected_goals_per_90")
        )

        xa90 = safe_float(
            p.get("expected_assists_per_90")
        )

        xgi90 = safe_float(
            p.get("expected_goal_involvements_per_90")
        )

        clean_sheets90 = safe_float(
            p.get("clean_sheets_per_90")
        )

        defensive90 = safe_float(
            p.get("defensive_contribution_per_90")
        )

        saves90 = safe_float(
            p.get("saves_per_90")
        )

        # Minutes reliability:
        # 3420 = 38 full matches
        minutes_factor = min(minutes / 3420, 1.0)

        # Reliability for per-90 stats.
        # Full strength at 1800+ minutes, heavily reduced for tiny samples.
        per90_reliability = min(minutes / 1800, 1.0)

        xg90_adj = xg90 * per90_reliability
        xa90_adj = xa90 * per90_reliability
        xgi90_adj = xgi90 * per90_reliability
        clean_sheets90_adj = clean_sheets90 * per90_reliability
        defensive90_adj = defensive90 * per90_reliability
        saves90_adj = saves90 * per90_reliability

        # Initial rating.
        fixture_score = fixture_scores.get(
            p["team"],
            0.0
        )

        position = positions[p["element_type"]]

        #
        # Base score shared by all positions
        #
        base_rating = (
            ep_next * 4.0
            + season_points_per_game * 3.0
            + minutes_factor * 3.0
            + fixture_score * 1.2
        )

        #
        # Position-specific upside
        #
        if position == "GKP":

            position_rating = (
                clean_sheets90_adj * 8.0
                + saves90_adj * 1.5
            )

        elif position == "DEF":

            position_rating = (
                clean_sheets90_adj * 7.0
                + xgi90_adj * 12.0
                + defensive90_adj * 0.30
            )

        elif position == "MID":

            position_rating = (
                xgi90_adj * 15.0
                + xg90_adj * 5.0
                + xa90_adj * 5.0
                + defensive90_adj * 0.15
            )

        elif position == "FWD":

            position_rating = (
                xgi90_adj * 18.0
                + xg90_adj * 7.0
                + xa90_adj * 3.0
            )

        else:

            position_rating = 0.0

        rating = (
            base_rating
            + position_rating
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
            "fixture_score": fixture_score,
            "fixtures": fixture_details.get(
                p["team"],
                []
            ),
            "rating": rating,
            "xg90": xg90,
            "xa90": xa90,
            "xgi90": xgi90,
            "clean_sheets90": clean_sheets90,
            "defensive90": defensive90,
            "saves90": saves90,
        })

    return players

def optimise_squad(players, force_player_id=None):

    problem = pulp.LpProblem(
        "FPL_GW1_Squad",
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
    # Starter gets full value.
    #
    # Captain gets another full copy of their score,
    # because captain points are doubled.
    #
    # A bench player gets 15% of their score so that
    # the optimiser doesn't completely ignore bench quality.
    #

    STARTER_WEIGHT = 1.0
    BENCH_WEIGHT = 0.15
    CAPTAIN_WEIGHT = 1.0

    problem += pulp.lpSum(
        (
            starter[p["id"]] * p["rating"] * STARTER_WEIGHT
            +
            (selected[p["id"]] - starter[p["id"]])
            * p["rating"]
            * BENCH_WEIGHT
            +
            captain[p["id"]]
            * p["rating"]
            * CAPTAIN_WEIGHT
        )
        for p in players
    )

    #
    # SQUAD RULES
    #

    # Exactly 15 players
    problem += pulp.lpSum(
        selected[p["id"]]
        for p in players
    ) == 15

    # £100.0m budget
    problem += pulp.lpSum(
        selected[p["id"]] * p["cost"]
        for p in players
    ) <= BUDGET

    # Squad position requirements
    squad_positions = {
        "GKP": 2,
        "DEF": 5,
        "MID": 5,
        "FWD": 3,
    }

    for position, required in squad_positions.items():
        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["position"] == position
        ) == required

    # Maximum 3 players from one club
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

    #
    # STARTING XI RULES
    #

    # Exactly 11 starters
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
    ) == 11

    # A starter must be in the squad
    for p in players:
        problem += (
            starter[p["id"]]
            <= selected[p["id"]]
        )

    # Exactly one starting goalkeeper
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "GKP"
    ) == 1

    # Minimum 3 defenders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "DEF"
    ) >= 3

    # Maximum 5 defenders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "DEF"
    ) <= 5

    # Minimum 2 midfielders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "MID"
    ) >= 2

    # Maximum 5 midfielders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "MID"
    ) <= 5

    # Minimum 1 forward
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "FWD"
    ) >= 1

    # Maximum 3 forwards
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "FWD"
    ) <= 3

    #
    # CAPTAIN RULES
    #

    # Exactly one captain
    problem += pulp.lpSum(
        captain[p["id"]]
        for p in players
    ) == 1

    # Captain must be a starter
    for p in players:
        problem += (
            captain[p["id"]]
            <= starter[p["id"]]
        )
    
    #
    # OPTIONAL FORCED PLAYER
    #

    if force_player_id is not None:
        problem += selected[force_player_id] == 1
    #
    # SOLVE
    #

    problem.solve(
        pulp.COIN_CMD(
            path="/usr/bin/cbc",
            msg=False
        )
    )

    if pulp.LpStatus[problem.status] != "Optimal":
        raise RuntimeError(
            f"Optimisation failed: "
            f"{pulp.LpStatus[problem.status]}"
        )

    squad = []

    for p in players:

        if selected[p["id"]].value() == 1:

            player = p.copy()

            player["starter"] = (
                starter[p["id"]].value() == 1
            )

            player["captain"] = (
                captain[p["id"]].value() == 1
            )

            squad.append(player)

    return squad

def calculate_objective_score(squad):

    STARTER_WEIGHT = 1.0
    BENCH_WEIGHT = 0.15
    CAPTAIN_WEIGHT = 1.0

    score = 0.0

    for p in squad:

        if p["starter"]:
            score += p["rating"] * STARTER_WEIGHT
        else:
            score += p["rating"] * BENCH_WEIGHT

        if p["captain"]:
            score += p["rating"] * CAPTAIN_WEIGHT

    return score

def compare_squads(base_squad, forced_squad, forced_player):

    base_score = calculate_objective_score(base_squad)
    forced_score = calculate_objective_score(forced_squad)

    base_ids = {
        p["id"]
        for p in base_squad
    }

    forced_ids = {
        p["id"]
        for p in forced_squad
    }

    added = [
        p
        for p in forced_squad
        if p["id"] not in base_ids
    ]

    removed = [
        p
        for p in base_squad
        if p["id"] not in forced_ids
    ]

    print()
    print("-" * 92)
    print(
        f"COMPARISON: FORCE {forced_player['name'].upper()} INTO SQUAD"
    )
    print("-" * 92)

    print(
        f"Normal squad score : {base_score:.2f}"
    )

    print(
        f"Forced squad score : {forced_score:.2f}"
    )

    difference = forced_score - base_score

    print(
        f"Difference         : {difference:+.2f}"
    )

    print()
    print("PLAYERS ADDED")
    print("-" * 50)

    for p in added:
        starter = "START" if p["starter"] else "BENCH"
        captain = " (C)" if p["captain"] else ""

        print(
            f"{p['name']:18} "
            f"{p['position']:3} "
            f"£{p['price']:4.1f}m "
            f"{starter:5}"
            f"{captain}"
        )

    print()
    print("PLAYERS REMOVED")
    print("-" * 50)

    for p in removed:
        starter = "START" if p["starter"] else "BENCH"
        captain = " (C)" if p["captain"] else ""

        print(
            f"{p['name']:18} "
            f"{p['position']:3} "
            f"£{p['price']:4.1f}m "
            f"{starter:5}"
            f"{captain}"
        )

    print()

    if difference > 0.01:

        print(
            f"RESULT: Including {forced_player['name']} "
            f"improves the model by {difference:.2f}."
        )

    elif difference < -0.01:

        print(
            f"RESULT: Including {forced_player['name']} "
            f"reduces the model by {abs(difference):.2f}."
        )

    else:

        print(
            "RESULT: The two squad structures are essentially equal."
        )

def print_squad(squad):

    position_order = {
        "GKP": 1,
        "DEF": 2,
        "MID": 3,
        "FWD": 4,
    }

    starters = [
        p for p in squad
        if p["starter"]
    ]

    bench = [
        p for p in squad
        if not p["starter"]
    ]

    starters.sort(
        key=lambda p: (
            position_order[p["position"]],
            -p["rating"]
        )
    )

    bench.sort(
        key=lambda p: (
            position_order[p["position"]],
            -p["rating"]
        )
    )

    total_cost = sum(
        p["cost"]
        for p in squad
    )

    print()
    print("=" * 92)
    print("                         FPL GW1 OPTIMISED TEAM")
    print("=" * 92)

    print()
    print("STARTING XI")
    print("-" * 92)

    current_position = None

    for p in starters:

        if p["position"] != current_position:
            current_position = p["position"]

            names = {
                "GKP": "GOALKEEPER",
                "DEF": "DEFENDERS",
                "MID": "MIDFIELDERS",
                "FWD": "FORWARDS",
            }

            print()
            print(names[current_position])

        captain_marker = ""

        if p["captain"]:
            captain_marker = "  (C)"

        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"£{p['price']:4.1f}m   "
            f"EP {p['ep_next']:4.1f}   "
            f"PPG {p['points_per_game']:4.1f}   "
            f"xGI90 {p['xgi90']:4.2f}   "
            f"FIX {p['fixture_score']:4.1f}   "
            f"Owned {p['ownership']:5.1f}%   "
            f"Score {p['rating']:5.1f}"
            f"{captain_marker}"
        )

    print()
    print("BENCH")
    print("-" * 92)

    for number, p in enumerate(bench, start=1):

        print(
            f"{number}. "
            f"{p['name']:16} "
            f"{p['team']:18} "
            f"{p['position']:3} "
            f"£{p['price']:4.1f}m   "
            f"EP {p['ep_next']:4.1f}   "
            f"Score {p['rating']:5.1f}"
        )

    captain_player = next(
        p for p in squad
        if p["captain"]
    )

    print()
    print("=" * 92)
    print(
        f"Captain    : "
        f"{captain_player['name']} "
        f"({captain_player['team']})"
    )
    print(
        f"Squad cost : "
        f"£{total_cost / 10:.1f}m"
    )
    print(
        f"In bank    : "
        f"£{(BUDGET - total_cost) / 10:.1f}m"
    )
    print("=" * 92)

if __name__ == "__main__":

    print("Downloading live FPL data...")

    players = load_players()

    print(
        f"Considering {len(players)} selectable players..."
    )

    #
    # Normal optimisation
    #

    squad = optimise_squad(players)

    print_squad(squad)

    #
    # Premium player comparisons
    #

    comparison_players = [
        ("Haaland", "Man City"),
        ("Saka", "Arsenal"),
        ("Palmer", "Chelsea"),
    ]

    for player_name, team_name in comparison_players:

        comparison_player = next(
            (
                p
                for p in players
                if p["name"] == player_name
                and p["team"] == team_name
            ),
            None
        )

        if comparison_player is None:
            continue

        already_selected = any(
            p["id"] == comparison_player["id"]
            for p in squad
        )

        print()
        print("=" * 92)

        if already_selected:

            print(
                f"{comparison_player['name']} is already "
                f"in the optimal squad."
            )

            continue

        alternative_squad = optimise_squad(
            players,
            force_player_id=comparison_player["id"]
        )

        print()
        print(
            f"{comparison_player['name'].upper()} ALTERNATIVE"
        )

        print_squad(alternative_squad)

        compare_squads(
            squad,
            alternative_squad,
            comparison_player
        )

