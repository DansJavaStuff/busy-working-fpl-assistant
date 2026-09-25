from history_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_database,
)


def historical_gameweek_context(
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
                name,
                short_name
            FROM teams
            WHERE season_id = ?
            ORDER BY name
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
                away_team_id
            FROM fixtures
            WHERE season_id = ?
              AND gameweek_id IS NOT NULL
            """,
            (
                season_id,
            ),
        ).fetchall()

    team_names = {
        int(team["id"]):
            (
                team["short_name"]
                or team["name"]
            )
        for team in teams
    }

    by_gameweek = {
        int(gameweek["id"]): {
            "gameweek":
                int(
                    gameweek[
                        "gameweek"
                    ]
                ),
            "counts": {
                team_id: 0
                for team_id
                in team_names
            },
        }
        for gameweek in gameweeks
    }

    for fixture in fixtures:
        item = by_gameweek.get(
            int(
                fixture[
                    "gameweek_id"
                ]
            )
        )

        if item is None:
            continue

        for column in (
            "home_team_id",
            "away_team_id",
        ):
            team_id = fixture[
                column
            ]

            if team_id is None:
                continue

            team_id = int(
                team_id
            )

            if team_id in item[
                "counts"
            ]:
                item["counts"][
                    team_id
                ] += 1

    result = []

    for item in sorted(
        by_gameweek.values(),
        key=lambda row:
            row["gameweek"],
    ):
        blank_ids = [
            team_id
            for team_id, count
            in item["counts"].items()
            if count == 0
        ]
        double_ids = [
            team_id
            for team_id, count
            in item["counts"].items()
            if count >= 2
        ]

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
            "gameweek":
                item["gameweek"],
            "kind":
                kind,
            "blank_team_count":
                len(blank_ids),
            "double_team_count":
                len(double_ids),
            "max_fixtures":
                max(
                    item[
                        "counts"
                    ].values(),
                    default=0,
                ),
            "blank_teams": [
                team_names[
                    team_id
                ]
                for team_id
                in blank_ids
            ],
            "double_teams": [
                team_names[
                    team_id
                ]
                for team_id
                in double_ids
            ],
        })

    return result


def historical_special_gameweeks(
    season_key,
    db_path=DEFAULT_DB_PATH,
):
    return [
        item
        for item in (
            historical_gameweek_context(
                season_key,
                db_path=db_path,
            )
        )
        if item["kind"] != "normal"
    ]
