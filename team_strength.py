from pathlib import Path
import csv
from collections import defaultdict


BASE = Path(
    "external/FPL-Core-Insights/data/2025-2026"
)


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalise_id(value):
    return str(
        int(float(value))
    )


def load_historical_team_names():

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

            #
            # matches.csv uses the team CODE,
            # not FPL id or pulse_id.
            #
            raw_id = row.get("code")
            name = row.get("name")

            if raw_id and name:
                teams[
                    normalise_id(raw_id)
                ] = name

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


def load_historical_matches():

    matches = {}

    for path in find_match_files():

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

                match_id = row.get(
                    "match_id"
                )

                if not match_id:
                    continue

                #
                # De-duplicate snapshots.
                #
                matches[
                    match_id
                ] = row

    return list(
        matches.values()
    )


def aggregate_team_xg(matches):

    stats = defaultdict(
        lambda: {
            "matches": 0,
            "xg_for": 0.0,
            "xg_against": 0.0,
        }
    )

    for match in matches:

        home = normalise_id(
            match["home_team"]
        )

        away = normalise_id(
            match["away_team"]
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

        #
        # Home team
        #
        stats[home]["matches"] += 1
        stats[home]["xg_for"] += home_xg
        stats[home]["xg_against"] += away_xg

        #
        # Away team
        #
        stats[away]["matches"] += 1
        stats[away]["xg_for"] += away_xg
        stats[away]["xg_against"] += home_xg

    return stats


def calculate_team_strengths(stats):

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
            "No historical Premier League "
            "match data found."
        )

    league_xg_per_team_match = (
        total_xg
        / total_matches
    )

    strengths = {}

    for team_id, s in stats.items():

        matches = s["matches"]

        if matches == 0:
            continue

        xg_for_pg = (
            s["xg_for"]
            / matches
        )

        xg_against_pg = (
            s["xg_against"]
            / matches
        )

        attack_strength = (
            xg_for_pg
            / league_xg_per_team_match
        )

        if xg_against_pg > 0:

            defence_strength = (
                league_xg_per_team_match
                / xg_against_pg
            )

        else:
            defence_strength = 1.0

        strengths[team_id] = {
            "matches": matches,
            "xg_for_pg": xg_for_pg,
            "xg_against_pg": xg_against_pg,
            "attack_strength": attack_strength,
            "defence_strength": defence_strength,
        }

    return strengths


def get_team_strengths():

    names = (
        load_historical_team_names()
    )

    matches = (
        load_historical_matches()
    )

    stats = (
        aggregate_team_xg(matches)
    )

    raw_strengths = (
        calculate_team_strengths(stats)
    )

    #
    # Return keyed by TEAM NAME rather
    # than historical IDs.
    #
    # This is important because FPL IDs/codes
    # can change between seasons.
    #
    strengths_by_name = {}

    for team_id, values in (
        raw_strengths.items()
    ):

        team_name = names.get(
            team_id
        )

        if not team_name:
            continue

        strengths_by_name[
            team_name
        ] = values

    return strengths_by_name


def damp_strength(
    value,
    weight=0.5
):
    """
    Pull extreme team-strength values
    halfway back towards league average.

    1.00 stays 1.00
    1.40 becomes 1.20
    0.60 becomes 0.80
    """

    return (
        1.0
        + (
            (value - 1.0)
            * weight
        )
    )


def attacking_fixture_multiplier(
    opponent_defence_strength
):
    """
    Strong opponent defence makes attacking
    points harder to obtain.
    """

    adjusted = damp_strength(
        opponent_defence_strength
    )

    return 1.0 / adjusted


def defensive_fixture_multiplier(
    opponent_attack_strength
):
    """
    Strong opponent attack makes defensive
    points harder to obtain.
    """

    adjusted = damp_strength(
        opponent_attack_strength
    )

    return 1.0 / adjusted


if __name__ == "__main__":

    strengths = get_team_strengths()

    rows = sorted(
        strengths.items(),
        key=lambda item:
        item[1]["attack_strength"],
        reverse=True
    )

    print()
    print(
        f"{'Team':20} "
        f"{'ATT':>6} "
        f"{'DEF':>6} "
        f"{'xG/G':>6} "
        f"{'xGA/G':>6}"
    )

    print("-" * 52)

    for name, s in rows:

        print(
            f"{name:20} "
            f"{s['attack_strength']:6.2f} "
            f"{s['defence_strength']:6.2f} "
            f"{s['xg_for_pg']:6.2f} "
            f"{s['xg_against_pg']:6.2f}"
        )
