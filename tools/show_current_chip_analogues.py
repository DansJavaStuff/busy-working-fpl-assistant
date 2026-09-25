import argparse

from historical_analogues import (
    current_historical_analogues,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare a current/future "
            "Gameweek with historical "
            "FH, BB or TC fixture patterns."
        )
    )

    parser.add_argument(
        "gameweek",
        type=int,
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

    result = (
        current_historical_analogues(
            args.chip,
            args.gameweek,
            limit=args.limit,
        )
    )

    current = result["current"]

    print(
        f"GW{args.gameweek} "
        f"{args.chip} pattern"
    )
    print(
        f"{current['kind']} · "
        f"{current['blank_team_count']} blank · "
        f"{current['double_team_count']} double · "
        f"{current['premium_blank_count']} premium blank · "
        f"{current['premium_double_count']} premium double"
    )

    if not result["analogues"]:
        print(
            "No non-zero historical "
            "analogues are available."
        )
        return

    print()
    print(
        "Closest historical analogues"
    )

    signal_key = {
        "FH":
            "free_hit_signal",
        "BB":
            "bench_boost_signal",
        "TC":
            "triple_captain_signal",
    }[args.chip]

    for row in result["analogues"]:
        print(
            f"{row['season']} "
            f"GW{row['gameweek']}: "
            f"{row['similarity']:.1f}% similar · "
            f"historical signal "
            f"{row[signal_key]:.1f} · "
            f"{row['kind']}"
        )


if __name__ == "__main__":
    main()
