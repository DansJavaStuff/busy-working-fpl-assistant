import argparse

from historical_context import (
    historical_special_gameweeks,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Show imported historical "
            "blank/double Gameweek context."
        )
    )
    parser.add_argument(
        "season",
        help=(
            "Season key such as 2025-26."
        ),
    )
    args = parser.parse_args()

    rows = historical_special_gameweeks(
        args.season
    )

    if not rows:
        print(
            "No special Gameweeks found "
            f"for {args.season}."
        )
        return

    for row in rows:
        print(
            f"GW{row['gameweek']}: "
            f"{row['kind']} · "
            f"{row['blank_team_count']} blank · "
            f"{row['double_team_count']} double"
        )


if __name__ == "__main__":
    main()
