import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from optimizer import (
    load_players,
    calculate_captain_score,
)

PLAYER_NAMES = [
    "Tzolakis",
    "Ajayi",
    "Cherki",
    "Haaland",
    "Raya",
]


def print_player(player):
    debug = player["projection_debug"]
    gw = player["planning_gameweek"]

    fixture = next(
        (
            f
            for f in player["fixtures"]
            if f["gw"] == gw
        ),
        None,
    )

    print()
    print("=" * 78)
    print(
        f"{player['name']} "
        f"({player['team']} - "
        f"{player['position']})"
    )
    print("=" * 78)

    print(
        f"Price                    : "
        f"£{player['price']:.1f}m"
    )

    print(
        f"Current PPG              : "
        f"{debug['ppg']:.2f}"
    )

    print(
        f"FPL ep_next              : "
        f"{debug['ep_next']:.2f}"
    )

    print(
        f"Minutes                  : "
        f"{player['minutes']}"
    )

    print(
        f"Current-season weight    : "
        f"{debug['current_season_weight']:.3f}"
    )

    print(
        f"Adjusted PPG             : "
        f"{debug['adjusted_ppg']:.2f}"
    )

    print(
        f"Historical baseline      : "
        f"{debug['historical_baseline']:.2f}"
    )

    print(
        f"Underlying adjustment    : "
        f"{debug['underlying_adjustment']:.2f}"
    )

    print(
        f"Projected baseline       : "
        f"{debug['projected_baseline']:.2f}"
    )

    print(
        f"Expected start prob.     : "
        f"{debug['expected_start_probability']:.2f}"
    )

    print(
        f"Availability             : "
        f"{player.get('chance_of_playing_next_round')}"
    )

    print(
        f"RotoWire status          : "
        f"{player.get('rotowire_status')}"
    )

    if fixture:

        venue = (
            "HOME"
            if fixture["home"]
            else "AWAY"
        )

        print()
        print("FIXTURE")
        print("-" * 78)

        print(
            f"Opponent                 : "
            f"{fixture['opponent_name']} "
            f"({venue})"
        )

        print(
            f"FPL difficulty           : "
            f"{fixture['difficulty']}"
        )

        print(
            f"Strength source           : "
            f"{fixture['strength_source']}"
        )

        print(
            f"Opponent attack          : "
            f"{fixture['opponent_attack']:.3f}"
        )

        print(
            f"Opponent defence         : "
            f"{fixture['opponent_defence']:.3f}"
        )

        print(
            f"Attack multiplier        : "
            f"{fixture['attack_multiplier']:.3f}"
        )

        print(
            f"Defence multiplier       : "
            f"{fixture['defence_multiplier']:.3f}"
        )

    print()
    print("PROJECTIONS")
    print("-" * 78)

    for future_gw in range(
        gw,
        gw + 5
    ):
        print(
            f"GW{future_gw:<2}                     : "
            f"{player.get(f'proj_gw{future_gw}', 0.0):.2f}"
        )

    print(
        f"5GW total                : "
        f"{player['proj_5gw']:.2f}"
    )

def print_captaincy_ranking(players):
    print()
    print()
    print("=" * 78)
    print("CAPTAINCY RANKING")
    print("=" * 78)

    ranked = sorted(
        players,
        key=calculate_captain_score,
        reverse=True,
    )

    print(
        f"{'Rank':<5} "
        f"{'Player':<20} "
        f"{'Pos':<5} "
        f"{'GW':>6} "
        f"{'Mult':>6} "
        f"{'Captain':>9}"
    )

    print("-" * 78)

    multipliers = {
        "FWD": 1.15,
        "MID": 1.12,
        "DEF": 1.03,
        "GKP": 0.95,
    }

    for rank, player in enumerate(
        ranked[:20],
        start=1,
    ):
        gw = player["planning_gameweek"]

        projection = player.get(
            f"proj_gw{gw}",
            0.0,
        )

        multiplier = multipliers.get(
            player["position"],
            1.0,
        )

        captain_score = (
            calculate_captain_score(
                player
            )
        )

        print(
            f"{rank:<5} "
            f"{player['name']:<20} "
            f"{player['position']:<5} "
            f"{projection:>6.2f} "
            f"{multiplier:>6.2f} "
            f"{captain_score:>9.2f}"
        )

if __name__ == "__main__":

    print(
        "Loading projection data..."
    )

    players = load_players()

    for name in PLAYER_NAMES:

        player = next(
            (
                p
                for p in players
                if p["name"] == name
            ),
            None,
        )

        if player is None:

            print()
            print(
                f"WARNING: "
                f"{name} not found"
            )

            continue

        print_player(player)
    print_captaincy_ranking(players)
