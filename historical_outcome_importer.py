import requests

from historical_importer import (
    DEFAULT_SEASONS,
    DEFAULT_SOURCE_REF,
    SOURCE_REPO,
    _fetch_csv,
    _optional_int,
    parse_season_key,
    resolve_source_commit,
)
from history_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_database,
    get_historical_imports,
    record_historical_import,
    transaction,
    upsert_gameweek,
    upsert_season,
    utc_now_iso,
)






def _existing_source_commit(
    seasons,
    db_path,
):
    wanted = {
        str(season)
        for season in seasons
    }

    imports = get_historical_imports(
        db_path=db_path
    )

    commits = {
        row["resolved_commit"]
        for row in imports
        if row["season_key"] in wanted
        and row["source_repo"]
        == SOURCE_REPO
        and row.get(
            "resolved_commit"
        )
    }

    if len(commits) == 1:
        return next(
            iter(commits)
        )

    return None


def _aggregate_rows(rows):
    grouped = {}

    for row in rows:
        element = _optional_int(
            row.get("element")
        )
        gameweek = _optional_int(
            row.get("GW")
            or row.get("round")
        )

        if (
            element is None
            or gameweek is None
        ):
            continue

        key = (
            gameweek,
            element,
        )

        item = grouped.setdefault(
            key,
            {
                "gameweek":
                    gameweek,
                "element":
                    element,
                "name":
                    row.get("name")
                    or f"Player {element}",
                "position":
                    row.get("position"),
                "team":
                    row.get("team"),
                "total_points":
                    0,
                "minutes":
                    0,
                "starts":
                    0,
                "value":
                    None,
                "selected":
                    None,
                "fixture_rows":
                    0,
            },
        )

        item["total_points"] += (
            _optional_int(
                row.get("total_points")
            )
            or 0
        )
        item["minutes"] += (
            _optional_int(
                row.get("minutes")
            )
            or 0
        )
        item["starts"] += (
            _optional_int(
                row.get("starts")
            )
            or 0
        )
        item["fixture_rows"] += 1

        value = _optional_int(
            row.get("value")
        )
        if value is not None:
            item["value"] = value

        selected = _optional_int(
            row.get("selected")
        )
        if selected is not None:
            item["selected"] = selected

    return list(
        grouped.values()
    )


def import_historical_player_outcomes(
    season_key,
    source_ref=DEFAULT_SOURCE_REF,
    resolved_commit=None,
    session=None,
    db_path=DEFAULT_DB_PATH,
):
    start_year, end_year = (
        parse_season_key(
            season_key
        )
    )

    session = (
        session
        or requests.Session()
    )

    if resolved_commit is None:
        resolved_commit = (
            _existing_source_commit(
                [season_key],
                db_path,
            )
            or resolve_source_commit(
                source_ref,
                session=session,
            )
        )

    ensure_database(
        db_path
    )

    rows = _fetch_csv(
        season_key,
        "gws/merged_gw.csv",
        resolved_commit,
        session,
    )

    aggregated = _aggregate_rows(
        rows
    )

    season_id = upsert_season(
        season_key,
        start_year,
        end_year,
        source=SOURCE_REPO,
        db_path=db_path,
    )

    gameweek_ids = {}

    for gameweek in range(
        1,
        39,
    ):
        gameweek_ids[gameweek] = (
            upsert_gameweek(
                season_id,
                gameweek,
                finished=True,
                data_checked=True,
                db_path=db_path,
            )
        )

    imported_at = utc_now_iso()

    with transaction(
        db_path
    ) as connection:
        for row in aggregated:
            gameweek_id = (
                gameweek_ids.get(
                    row["gameweek"]
                )
            )

            if gameweek_id is None:
                continue

            connection.execute(
                """
                INSERT INTO historical_player_gameweeks (
                    season_id,
                    gameweek_id,
                    fpl_element_id,
                    player_name,
                    position,
                    team_name,
                    total_points,
                    minutes,
                    starts,
                    value,
                    selected,
                    fixture_rows,
                    source,
                    source_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    season_id,
                    gameweek_id,
                    fpl_element_id
                )
                DO UPDATE SET
                    player_name =
                        excluded.player_name,
                    position =
                        excluded.position,
                    team_name =
                        excluded.team_name,
                    total_points =
                        excluded.total_points,
                    minutes =
                        excluded.minutes,
                    starts =
                        excluded.starts,
                    value =
                        excluded.value,
                    selected =
                        excluded.selected,
                    fixture_rows =
                        excluded.fixture_rows,
                    source =
                        excluded.source,
                    source_updated_at =
                        excluded.source_updated_at
                """,
                (
                    season_id,
                    gameweek_id,
                    row["element"],
                    row["name"],
                    row["position"],
                    row["team"],
                    row["total_points"],
                    row["minutes"],
                    row["starts"],
                    row["value"],
                    row["selected"],
                    row["fixture_rows"],
                    SOURCE_REPO,
                    imported_at,
                ),
            )

    record_historical_import(
        season_id,
        SOURCE_REPO,
        source_ref,
        resolved_commit,
        [
            (
                f"data/{season_key}/"
                "gws/merged_gw.csv"
            )
        ],
        imported_at=imported_at,
        db_path=db_path,
    )

    return {
        "season":
            season_key,
        "resolved_commit":
            resolved_commit,
        "rows":
            len(aggregated),
        "gameweeks":
            len({
                row["gameweek"]
                for row in aggregated
            }),
    }


def import_historical_player_outcomes_all(
    seasons=DEFAULT_SEASONS,
    source_ref=DEFAULT_SOURCE_REF,
    resolved_commit=None,
    session=None,
    db_path=DEFAULT_DB_PATH,
):
    session = (
        session
        or requests.Session()
    )

    if resolved_commit is None:
        resolved_commit = (
            _existing_source_commit(
                seasons,
                db_path,
            )
            or resolve_source_commit(
                source_ref,
                session=session,
            )
        )

    results = []

    for season in seasons:
        results.append(
            import_historical_player_outcomes(
                season,
                source_ref=source_ref,
                resolved_commit=
                    resolved_commit,
                session=session,
                db_path=db_path,
            )
        )

    return {
        "source_repo":
            SOURCE_REPO,
        "requested_ref":
            source_ref,
        "resolved_commit":
            resolved_commit,
        "seasons":
            results,
    }


def load_historical_player_gameweek(
    season_key,
    gameweek,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                historical_player_gameweeks.fpl_element_id,
                historical_player_gameweeks.player_name,
                historical_player_gameweeks.position,
                historical_player_gameweeks.team_name,
                historical_player_gameweeks.total_points,
                historical_player_gameweeks.minutes,
                historical_player_gameweeks.starts,
                historical_player_gameweeks.value,
                historical_player_gameweeks.selected,
                historical_player_gameweeks.fixture_rows
            FROM historical_player_gameweeks
            JOIN seasons
              ON seasons.id =
                 historical_player_gameweeks.season_id
            JOIN gameweeks
              ON gameweeks.id =
                 historical_player_gameweeks.gameweek_id
            WHERE seasons.season_key = ?
              AND gameweeks.gameweek = ?
            ORDER BY
                historical_player_gameweeks.total_points DESC,
                historical_player_gameweeks.fpl_element_id
            """,
            (
                season_key,
                int(gameweek),
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]
