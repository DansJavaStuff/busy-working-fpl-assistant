import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from optimizer import load_players


TARGETS = {
    "Hinshelwood",
    "Haaland",
    "Groß",
    "Bogle",
}


def main():
    players = load_players(
        projection_end_gameweek=19,
        long_range_regression=True,
    )

    selected = [
        player
        for player in players
        if player["name"] in TARGETS
    ]

    selected.sort(
        key=lambda player:
            player["name"]
    )

    for player in selected:
        debug = player.get(
            "projection_debug",
            {},
        )

        print()
        print("=" * 88)
        print(
            f"{player['name']} · "
            f"{player['team']} · "
            f"{player['position']}"
        )
        print("=" * 88)

        print(
            "PPG:",
            debug.get("ppg"),
        )
        print(
            "Historical baseline:",
            debug.get(
                "historical_baseline"
            ),
        )
        print(
            "Historical PPG:",
            debug.get(
                "historical_ppg"
            ),
        )
        print(
            "Historical minutes:",
            debug.get(
                "historical_minutes"
            ),
        )
        print(
            "Historical reliability:",
            debug.get(
                "historical_reliability"
            ),
        )
        print(
            "Current-season weight:",
            debug.get(
                "current_season_weight"
            ),
        )
        print(
            "Adjusted PPG:",
            debug.get(
                "adjusted_ppg"
            ),
        )
        print(
            "Underlying adjustment:",
            debug.get(
                "underlying_adjustment"
            ),
        )
        print(
            "Projected baseline:",
            debug.get(
                "projected_baseline"
            ),
        )
        print(
            "Expected start probability:",
            debug.get(
                "expected_start_probability"
            ),
        )

        print()
        print("GAMEWEEK PROJECTIONS")
        print("-" * 88)

        fixtures = {
            fixture["gw"]: fixture
            for fixture
            in player.get(
                "fixtures",
                [],
            )
        }

        for gw in range(6, 20):
            projection = player.get(
                f"proj_gw{gw}"
            )

            if projection is None:
                continue

            fixture = fixtures.get(
                gw,
                {},
            )

            opponent = fixture.get(
                "opponent_name",
                "—",
            )

            venue = (
                "H"
                if fixture.get("home")
                else "A"
            )

            multiplier = (
                fixture.get(
                    "attack_multiplier"
                )
                if player["position"]
                in {"MID", "FWD"}
                else fixture.get(
                    "defence_multiplier"
                )
            )

            print(
                f"GW{gw:<2} "
                f"{opponent:<18} "
                f"{venue} "
                f"mult="
                f"{multiplier!s:<8} "
                f"proj="
                f"{projection:.2f}"
            )


if __name__ == "__main__":
    main()
