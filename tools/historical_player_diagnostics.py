import csv
import sys
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATA_ROOT = (
    PROJECT_ROOT
    / "external"
    / "FPL-Core-Insights"
    / "data"
    / "2025-2026"
)

PLAYERS_FILE = (
    DATA_ROOT
    / "players.csv"
)

PLAYERSTATS_FILE = (
    DATA_ROOT
    / "playerstats.csv"
)


PLAYER_NAMES = [
    "Haaland",
    "Cherki",
    "B.Fernandes",
    "Saka",
    "Ajayi",
    "Tzolakis",
]


def load_csv(path):
    with path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def find_matches(rows, name):
    target = name.lower()

    matches = []

    for row in rows:

        searchable = " ".join(
            str(row.get(field, ""))
            for field in (
                "web_name",
                "first_name",
                "second_name",
                "name",
            )
        ).lower()

        if target in searchable:
            matches.append(row)

    return matches


def print_selected_fields(row):
    interesting = [
        "id",
        "player_id",
        "player_code",
        "first_name",
        "second_name",
        "web_name",
        "position",
        "team",
        "minutes",
        "starts",
        "total_points",
        "points_per_game",
        "goals_scored",
        "assists",
        "clean_sheets",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "saves",
        "bonus",
        "bps",
    ]

    for field in interesting:

        if field not in row:
            continue

        print(
            f"{field:<30}: "
            f"{row[field]}"
        )


def main():

    print(
        f"Players file     : "
        f"{PLAYERS_FILE}"
    )

    print(
        f"Playerstats file : "
        f"{PLAYERSTATS_FILE}"
    )

    print()

    if not PLAYERS_FILE.exists():

        print(
            "ERROR: players.csv not found"
        )

        sys.exit(1)

    if not PLAYERSTATS_FILE.exists():

        print(
            "ERROR: playerstats.csv not found"
        )

        sys.exit(1)

    players = load_csv(
        PLAYERS_FILE
    )

    stats = load_csv(
        PLAYERSTATS_FILE
    )

    print(
        f"Historical players loaded: "
        f"{len(players)}"
    )

    print(
        f"Historical stats rows     : "
        f"{len(stats)}"
    )

    for name in PLAYER_NAMES:

        print()
        print("=" * 78)
        print(name)
        print("=" * 78)

        player_matches = (
            find_matches(
                players,
                name,
            )
        )

        stat_matches = (
            find_matches(
                stats,
                name,
            )
        )

        print()
        print("PLAYERS.CSV")
        print("-" * 78)

        if not player_matches:

            print("No match")

        else:

            for row in player_matches[:5]:
                print_selected_fields(
                    row
                )
                print()

        print()
        print("PLAYERSTATS.CSV")
        print("-" * 78)

        if not stat_matches:

            print("No match")

        else:

            for row in stat_matches[-5:]:
                print_selected_fields(
                    row
                )
                print()


if __name__ == "__main__":
    main()
