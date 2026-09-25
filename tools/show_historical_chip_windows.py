import argparse

from historical_chip_features import (
    strongest_historical_windows,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Show historical fixture-pattern "
            "signals for FH, BB or TC."
        )
    )

    parser.add_argument(
        "season",
        help="Season such as 2025-26.",
    )
    parser.add_argument(
        "chip",
        choices=[
            "FH",
            "BB",
            "TC",
        ],
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    rows = strongest_historical_windows(
        args.season,
        args.chip,
        limit=args.limit,
    )

    signal_key = {
        "FH": "free_hit_signal",
        "BB": "bench_boost_signal",
        "TC": "triple_captain_signal",
    }[args.chip]

    for row in rows:
        print(
            f"GW{row['gameweek']}: "
            f"{row[signal_key]:.1f} · "
            f"{row['kind']} · "
            f"{row['blank_team_count']} blank · "
            f"{row['double_team_count']} double · "
            f"{row['premium_double_count']} premium double"
        )


if __name__ == "__main__":
    main()
