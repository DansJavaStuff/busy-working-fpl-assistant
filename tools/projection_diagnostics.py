import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from optimizer import load_players


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
