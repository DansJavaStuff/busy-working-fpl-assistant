from pathlib import Path
import csv
from collections import defaultdict


BASE = Path(
    "external/FPL-Core-Insights/data/2025-2026"
)


def safe_float(value):
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def load_team_names():

    teams_file = (
        BASE
        / "By Tournament"
        / "Premier League"
        / "GW1"
        / "teams.csv"
    )

    teams = {}

    with teams_file.open(
        newline="",
        encoding="utf-8-sig"
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            raw_id = row.get("code")

            name = (
                row.get("name")
                or row.get("team_name")
                or row.get("short_name")
            )

            if raw_id and name:

                team_id = str(
                    int(float(raw_id))
                )

                teams[team_id] = name

    return teams

def find_match_files():

    tournament_dir = (
        BASE
        / "By Tournament"
        / "Premier League"
    )

    return sorted(
        tournament_dir.glob(
            "GW*/matches.csv"
        )
    )

def load_matches():

    match_files = find_match_files()

    print(
        f"Found {len(match_files)} Premier League "
        f"match CSV files"
    )

    matches = {}

    for path in match_files:

        with path.open(
            newline="",
            encoding="utf-8-sig"
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:

                finished = str(
                    row.get("finished", "")
                ).lower()

                if finished not in {
                    "true",
                    "1",
                    "yes",
                }:
                    continue

                match_id = (
                    row.get("match_id")
                    or row.get("id")
                )

                if not match_id:
                    continue

                #
                # The repository contains snapshots,
                # so the same match may occur in more
                # than one file. match_id de-duplicates it.
                #
                matches[str(match_id)] = row

    return list(matches.values())


def aggregate_team_stats(matches):

    stats = defaultdict(
        lambda: {
            "matches": 0,
            "xg_for": 0.0,
            "xg_against": 0.0,
            "npxg_for": 0.0,
            "npxg_against": 0.0,
            "shots_for": 0,
            "shots_against": 0,
            "big_chances_for": 0,
            "big_chances_against": 0,
        }
    )

    for match in matches:

        home = str(
            int(float(match["home_team"]))
        )

        away = str(
            int(float(match["away_team"]))
        )

        home_xg = safe_float(
            match.get(
                "home_expected_goals_xg"
            )
        )

        away_xg = safe_float(
            match.get(
                "away_expected_goals_xg"
            )
        )

        home_npxg = safe_float(
            match.get("home_non_penalty_xg")
        )

        away_npxg = safe_float(
            match.get("away_non_penalty_xg")
        )

        home_shots = safe_float(
            match.get("home_total_shots")
        )

        away_shots = safe_float(
            match.get("away_total_shots")
        )

        home_big = safe_float(
            match.get("home_big_chances")
        )

        away_big = safe_float(
            match.get("away_big_chances")
        )

        #
        # HOME TEAM
        #
        stats[home]["matches"] += 1

        stats[home]["xg_for"] += home_xg
        stats[home]["xg_against"] += away_xg

        stats[home]["npxg_for"] += home_npxg
        stats[home]["npxg_against"] += away_npxg

        stats[home]["shots_for"] += home_shots
        stats[home]["shots_against"] += away_shots

        stats[home]["big_chances_for"] += home_big
        stats[home]["big_chances_against"] += away_big

        #
        # AWAY TEAM
        #
        stats[away]["matches"] += 1

        stats[away]["xg_for"] += away_xg
        stats[away]["xg_against"] += home_xg

        stats[away]["npxg_for"] += away_npxg
        stats[away]["npxg_against"] += home_npxg

        stats[away]["shots_for"] += away_shots
        stats[away]["shots_against"] += home_shots

        stats[away]["big_chances_for"] += away_big
        stats[away]["big_chances_against"] += home_big

    return stats

def calculate_strengths(stats):

    total_xg = sum(
        team["xg_for"]
        for team in stats.values()
    )

    total_matches = sum(
        team["matches"]
        for team in stats.values()
    )

    if total_matches == 0:
        raise RuntimeError(
            "No match data found. "
            "Check the external dataset path."
        )

    league_xg_per_team_match = (
        total_xg / total_matches
    )

    results = {}

    for team_id, s in stats.items():

        matches = s["matches"]

        if matches == 0:
            continue

        xg_for_pg = (
            s["xg_for"] / matches
        )

        xg_against_pg = (
            s["xg_against"] / matches
        )

        attack_strength = (
            xg_for_pg
            / league_xg_per_team_match
        )

        defence_strength = (
            league_xg_per_team_match
            / xg_against_pg
        )

        results[team_id] = {
            **s,
            "xg_for_pg": xg_for_pg,
            "xg_against_pg": xg_against_pg,
            "attack_strength": attack_strength,
            "defence_strength": defence_strength,
        }

    return results

def print_results(results, team_names):

    rows = []

    for team_id, s in results.items():

        rows.append({
            "team": team_names.get(
                team_id,
                f"Team {team_id}"
            ),
            **s,
        })

    rows.sort(
        key=lambda x:
        x["attack_strength"],
        reverse=True
    )

    print()
    print(
        f"{'Team':20} "
        f"{'MP':>3} "
        f"{'xG':>6} "
        f"{'xGA':>6} "
        f"{'xG/G':>6} "
        f"{'xGA/G':>6} "
        f"{'ATT':>6} "
        f"{'DEF':>6}"
    )

    print("-" * 72)

    for row in rows:

        print(
            f"{row['team']:20} "
            f"{row['matches']:3} "
            f"{row['xg_for']:6.1f} "
            f"{row['xg_against']:6.1f} "
            f"{row['xg_for_pg']:6.2f} "
            f"{row['xg_against_pg']:6.2f} "
            f"{row['attack_strength']:6.2f} "
            f"{row['defence_strength']:6.2f}"
        )


if __name__ == "__main__":

    team_names = load_team_names()

    matches = load_matches()

    print(
        f"Loaded {len(matches)} unique "
        f"finished Premier League matches"
    )

    stats = aggregate_team_stats(
        matches
    )

    results = calculate_strengths(
        stats
    )

    print_results(
        results,
        team_names
    )
