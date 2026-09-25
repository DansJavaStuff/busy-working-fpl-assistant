from statistics import mean

from history_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_database,
)


def _difficulty_quality(
    difficulty,
):
    if difficulty is None:
        return 0.0

    # FPL difficulty runs from 1 (easiest)
    # to 5 (hardest). Convert to a simple
    # 0..1 opportunity scale.
    difficulty = max(
        1,
        min(
            5,
            int(difficulty),
        ),
    )

    return (
        5 - difficulty
    ) / 4


def historical_chip_features(
    season_key,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        season = connection.execute(
            """
            SELECT id
            FROM seasons
            WHERE season_key = ?
            """,
            (
                season_key,
            ),
        ).fetchone()

        if season is None:
            return []

        season_id = int(
            season["id"]
        )

        teams = connection.execute(
            """
            SELECT
                id,
                fpl_team_id,
                name,
                short_name,
                strength
            FROM teams
            WHERE season_id = ?
            """,
            (
                season_id,
            ),
        ).fetchall()

        gameweeks = connection.execute(
            """
            SELECT
                id,
                gameweek
            FROM gameweeks
            WHERE season_id = ?
            ORDER BY gameweek
            """,
            (
                season_id,
            ),
        ).fetchall()

        fixtures = connection.execute(
            """
            SELECT
                gameweek_id,
                home_team_id,
                away_team_id,
                home_difficulty,
                away_difficulty
            FROM fixtures
            WHERE season_id = ?
              AND gameweek_id IS NOT NULL
            """,
            (
                season_id,
            ),
        ).fetchall()

    team_meta = {
        int(team["id"]): {
            "name":
                (
                    team["short_name"]
                    or team["name"]
                ),
            "strength":
                (
                    int(
                        team["strength"]
                    )
                    if team["strength"]
                    is not None
                    else 0
                ),
        }
        for team in teams
    }

    ranked = sorted(
        team_meta,
        key=lambda team_id: (
            -team_meta[
                team_id
            ]["strength"],
            team_meta[
                team_id
            ]["name"],
        ),
    )

    premium_team_ids = set(
        ranked[:6]
    )

    rows_by_gameweek = {
        int(row["id"]): {
            "gameweek":
                int(
                    row["gameweek"]
                ),
            "team_fixtures": {
                team_id: []
                for team_id
                in team_meta
            },
        }
        for row in gameweeks
    }

    for fixture in fixtures:
        item = rows_by_gameweek.get(
            int(
                fixture[
                    "gameweek_id"
                ]
            )
        )

        if item is None:
            continue

        home_team_id = (
            int(
                fixture[
                    "home_team_id"
                ]
            )
            if fixture[
                "home_team_id"
            ] is not None
            else None
        )
        away_team_id = (
            int(
                fixture[
                    "away_team_id"
                ]
            )
            if fixture[
                "away_team_id"
            ] is not None
            else None
        )

        if home_team_id in item[
            "team_fixtures"
        ]:
            item["team_fixtures"][
                home_team_id
            ].append(
                fixture[
                    "home_difficulty"
                ]
            )

        if away_team_id in item[
            "team_fixtures"
        ]:
            item["team_fixtures"][
                away_team_id
            ].append(
                fixture[
                    "away_difficulty"
                ]
            )

    result = []

    for item in sorted(
        rows_by_gameweek.values(),
        key=lambda row:
            row["gameweek"],
    ):
        counts = {
            team_id:
                len(fixtures_for_team)
            for team_id, fixtures_for_team
            in item[
                "team_fixtures"
            ].items()
        }

        blank_ids = {
            team_id
            for team_id, count
            in counts.items()
            if count == 0
        }
        double_ids = {
            team_id
            for team_id, count
            in counts.items()
            if count >= 2
        }

        premium_blank_ids = (
            blank_ids
            & premium_team_ids
        )
        premium_double_ids = (
            double_ids
            & premium_team_ids
        )

        double_qualities = []

        for team_id in double_ids:
            double_qualities.extend(
                _difficulty_quality(
                    difficulty
                )
                for difficulty
                in item[
                    "team_fixtures"
                ][team_id]
            )

        mean_double_fixture_quality = (
            mean(
                double_qualities
            )
            if double_qualities
            else 0.0
        )

        team_count = max(
            1,
            len(team_meta),
        )

        blank_share = (
            len(blank_ids)
            / team_count
        )
        double_share = (
            len(double_ids)
            / team_count
        )

        premium_blank_share = (
            len(
                premium_blank_ids
            )
            / max(
                1,
                len(
                    premium_team_ids
                ),
            )
        )
        premium_double_share = (
            len(
                premium_double_ids
            )
            / max(
                1,
                len(
                    premium_team_ids
                ),
            )
        )

        # These are fixture-pattern signals, not
        # estimates of realised chip points.
        free_hit_signal = round(
            100
            * (
                0.65 * blank_share
                + 0.35
                * premium_blank_share
            ),
            1,
        )

        bench_boost_signal = round(
            100
            * (
                0.50 * double_share
                + 0.30
                * premium_double_share
                + 0.20
                * mean_double_fixture_quality
            ),
            1,
        )

        triple_captain_signal = round(
            100
            * (
                0.60
                * premium_double_share
                + 0.40
                * mean_double_fixture_quality
            ),
            1,
        )

        if (
            blank_ids
            and double_ids
        ):
            kind = "blank_double"
        elif blank_ids:
            kind = "blank"
        elif double_ids:
            kind = "double"
        else:
            kind = "normal"

        result.append({
            "season":
                season_key,
            "gameweek":
                item["gameweek"],
            "kind":
                kind,
            "blank_team_count":
                len(blank_ids),
            "double_team_count":
                len(double_ids),
            "premium_blank_count":
                len(
                    premium_blank_ids
                ),
            "premium_double_count":
                len(
                    premium_double_ids
                ),
            "mean_double_fixture_quality":
                round(
                    mean_double_fixture_quality,
                    3,
                ),
            "free_hit_signal":
                free_hit_signal,
            "bench_boost_signal":
                bench_boost_signal,
            "triple_captain_signal":
                triple_captain_signal,
            "blank_teams":
                sorted(
                    team_meta[
                        team_id
                    ]["name"]
                    for team_id
                    in blank_ids
                ),
            "double_teams":
                sorted(
                    team_meta[
                        team_id
                    ]["name"]
                    for team_id
                    in double_ids
                ),
            "premium_blank_teams":
                sorted(
                    team_meta[
                        team_id
                    ]["name"]
                    for team_id
                    in premium_blank_ids
                ),
            "premium_double_teams":
                sorted(
                    team_meta[
                        team_id
                    ]["name"]
                    for team_id
                    in premium_double_ids
                ),
        })

    return result


def strongest_historical_windows(
    season_key,
    chip,
    limit=5,
    db_path=DEFAULT_DB_PATH,
):
    key_by_chip = {
        "freehit":
            "free_hit_signal",
        "fh":
            "free_hit_signal",
        "bboost":
            "bench_boost_signal",
        "bb":
            "bench_boost_signal",
        "3xc":
            "triple_captain_signal",
        "tc":
            "triple_captain_signal",
    }

    signal_key = key_by_chip.get(
        str(chip).lower()
    )

    if signal_key is None:
        raise ValueError(
            "Historical fixture-pattern "
            "signals currently support "
            "FH, BB and TC."
        )

    rows = historical_chip_features(
        season_key,
        db_path=db_path,
    )

    candidates = [
        row
        for row in rows
        if row[signal_key] > 0
    ]

    return sorted(
        candidates,
        key=lambda row: (
            -row[signal_key],
            row["gameweek"],
        ),
    )[:int(limit)]
