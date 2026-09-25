import csv
import io
import re

import requests

from history_store import (
    ensure_database,
    record_historical_import,
    transaction,
    upsert_gameweek,
    upsert_season,
    utc_now_iso,
)


SOURCE_REPO = (
    "vaastav/Fantasy-Premier-League"
)
SOURCE_API_BASE = (
    "https://api.github.com/repos/"
    f"{SOURCE_REPO}"
)
SOURCE_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    f"{SOURCE_REPO}"
)

DEFAULT_SOURCE_REF = "master"

DEFAULT_SEASONS = (
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
)

SEASON_PATTERN = re.compile(
    r"^(?P<start>\d{4})-(?P<end>\d{2})$"
)


class HistoricalImportError(
    RuntimeError
):
    pass


def _optional_int(value):
    if value in (
        None,
        "",
        "None",
        "null",
        "nan",
    ):
        return None

    return int(
        float(value)
    )


def _optional_bool(value):
    if value in (
        None,
        "",
        "None",
        "null",
        "nan",
    ):
        return None

    if isinstance(
        value,
        bool,
    ):
        return value

    normalised = str(
        value
    ).strip().lower()

    if normalised in {
        "1",
        "true",
        "yes",
    }:
        return True

    if normalised in {
        "0",
        "false",
        "no",
    }:
        return False

    raise HistoricalImportError(
        f"Unable to parse boolean: {value!r}"
    )


def parse_season_key(
    season_key,
):
    match = SEASON_PATTERN.fullmatch(
        str(
            season_key
        ).strip()
    )

    if match is None:
        raise HistoricalImportError(
            "Season must look like "
            "2025-26."
        )

    start_year = int(
        match.group("start")
    )
    expected_end = (
        start_year + 1
    ) % 100

    if int(
        match.group("end")
    ) != expected_end:
        raise HistoricalImportError(
            f"Season {season_key} does "
            "not span consecutive years."
        )

    return (
        start_year,
        start_year + 1,
    )


def resolve_source_commit(
    source_ref=DEFAULT_SOURCE_REF,
    session=None,
):
    session = (
        session
        or requests.Session()
    )

    url = (
        f"{SOURCE_API_BASE}/commits/"
        f"{source_ref}"
    )

    try:
        response = session.get(
            url,
            timeout=(5, 30),
            headers={
                "Accept":
                    "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        raise HistoricalImportError(
            "Unable to resolve historical "
            "dataset source commit."
        ) from exc

    commit = payload.get("sha")

    if not commit:
        raise HistoricalImportError(
            "Historical dataset source "
            "did not return a commit SHA."
        )

    return commit


def _fetch_csv(
    season_key,
    filename,
    resolved_commit,
    session,
):
    url = (
        f"{SOURCE_RAW_BASE}/"
        f"{resolved_commit}/data/"
        f"{season_key}/{filename}"
    )

    try:
        response = session.get(
            url,
            timeout=(5, 45),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HistoricalImportError(
            f"Unable to download "
            f"{season_key}/{filename}."
        ) from exc

    return list(
        csv.DictReader(
            io.StringIO(
                response.text
            )
        )
    )


def _upsert_teams(
    connection,
    season_id,
    team_rows,
):
    team_ids = {}

    for row in team_rows:
        fpl_team_id = _optional_int(
            row.get("id")
        )

        if fpl_team_id is None:
            continue

        connection.execute(
            """
            INSERT INTO teams (
                season_id,
                fpl_team_id,
                name,
                short_name,
                source,
                strength,
                strength_overall_home,
                strength_overall_away,
                strength_attack_home,
                strength_attack_away,
                strength_defence_home,
                strength_defence_away
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                season_id,
                fpl_team_id
            )
            DO UPDATE SET
                name =
                    excluded.name,
                short_name =
                    excluded.short_name,
                source =
                    excluded.source,
                strength =
                    excluded.strength,
                strength_overall_home =
                    excluded.strength_overall_home,
                strength_overall_away =
                    excluded.strength_overall_away,
                strength_attack_home =
                    excluded.strength_attack_home,
                strength_attack_away =
                    excluded.strength_attack_away,
                strength_defence_home =
                    excluded.strength_defence_home,
                strength_defence_away =
                    excluded.strength_defence_away
            """,
            (
                season_id,
                fpl_team_id,
                row.get("name")
                or f"Team {fpl_team_id}",
                row.get("short_name"),
                SOURCE_REPO,
                _optional_int(
                    row.get("strength")
                ),
                _optional_int(
                    row.get(
                        "strength_overall_home"
                    )
                ),
                _optional_int(
                    row.get(
                        "strength_overall_away"
                    )
                ),
                _optional_int(
                    row.get(
                        "strength_attack_home"
                    )
                ),
                _optional_int(
                    row.get(
                        "strength_attack_away"
                    )
                ),
                _optional_int(
                    row.get(
                        "strength_defence_home"
                    )
                ),
                _optional_int(
                    row.get(
                        "strength_defence_away"
                    )
                ),
            ),
        )

    rows = connection.execute(
        """
        SELECT id, fpl_team_id
        FROM teams
        WHERE season_id = ?
        """,
        (
            season_id,
        ),
    ).fetchall()

    for row in rows:
        team_ids[
            int(
                row["fpl_team_id"]
            )
        ] = int(
            row["id"]
        )

    return team_ids


def _gameweek_ids(
    season_id,
    db_path,
):
    result = {}

    for gameweek in range(
        1,
        39,
    ):
        result[gameweek] = (
            upsert_gameweek(
                season_id,
                gameweek,
                finished=True,
                data_checked=True,
                db_path=db_path,
            )
        )

    return result


def _upsert_fixtures(
    connection,
    season_id,
    fixture_rows,
    team_ids,
    gameweek_ids,
    source_updated_at,
):
    imported = 0
    unassigned = 0

    for row in fixture_rows:
        fixture_id = _optional_int(
            row.get("id")
        )
        home_fpl_id = _optional_int(
            row.get("team_h")
        )
        away_fpl_id = _optional_int(
            row.get("team_a")
        )
        event = _optional_int(
            row.get("event")
        )

        if (
            fixture_id is None
            or home_fpl_id is None
            or away_fpl_id is None
        ):
            continue

        home_team_id = team_ids.get(
            home_fpl_id
        )
        away_team_id = team_ids.get(
            away_fpl_id
        )

        if (
            home_team_id is None
            or away_team_id is None
        ):
            raise HistoricalImportError(
                "Fixture references an "
                "unknown historical team."
            )

        gameweek_id = (
            gameweek_ids.get(event)
            if event is not None
            else None
        )

        if event is None:
            unassigned += 1

        connection.execute(
            """
            INSERT INTO fixtures (
                season_id,
                fpl_fixture_id,
                gameweek_id,
                home_team_id,
                away_team_id,
                kickoff_time,
                home_difficulty,
                away_difficulty,
                home_score,
                away_score,
                finished,
                source,
                source_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                season_id,
                fpl_fixture_id
            )
            DO UPDATE SET
                gameweek_id =
                    excluded.gameweek_id,
                home_team_id =
                    excluded.home_team_id,
                away_team_id =
                    excluded.away_team_id,
                kickoff_time =
                    excluded.kickoff_time,
                home_difficulty =
                    excluded.home_difficulty,
                away_difficulty =
                    excluded.away_difficulty,
                home_score =
                    excluded.home_score,
                away_score =
                    excluded.away_score,
                finished =
                    excluded.finished,
                source =
                    excluded.source,
                source_updated_at =
                    excluded.source_updated_at
            """,
            (
                season_id,
                fixture_id,
                gameweek_id,
                home_team_id,
                away_team_id,
                row.get("kickoff_time"),
                _optional_int(
                    row.get(
                        "team_h_difficulty"
                    )
                ),
                _optional_int(
                    row.get(
                        "team_a_difficulty"
                    )
                ),
                _optional_int(
                    row.get(
                        "team_h_score"
                    )
                ),
                _optional_int(
                    row.get(
                        "team_a_score"
                    )
                ),
                (
                    None
                    if _optional_bool(
                        row.get("finished")
                    ) is None
                    else int(
                        _optional_bool(
                            row.get("finished")
                        )
                    )
                ),
                SOURCE_REPO,
                source_updated_at,
            ),
        )

        imported += 1

    return {
        "fixtures": imported,
        "unassigned_fixtures":
            unassigned,
    }


def import_historical_season(
    season_key,
    source_ref=DEFAULT_SOURCE_REF,
    resolved_commit=None,
    session=None,
    db_path=None,
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
            resolve_source_commit(
                source_ref,
                session=session,
            )
        )

    kwargs = {}

    if db_path is not None:
        kwargs["db_path"] = db_path

    ensure_database(
        **kwargs
    )

    team_rows = _fetch_csv(
        season_key,
        "teams.csv",
        resolved_commit,
        session,
    )
    fixture_rows = _fetch_csv(
        season_key,
        "fixtures.csv",
        resolved_commit,
        session,
    )

    season_id = upsert_season(
        season_key,
        start_year,
        end_year,
        source=SOURCE_REPO,
        **kwargs,
    )

    actual_db_path = (
        db_path
        if db_path is not None
        else None
    )

    gameweek_kwargs = {}

    if actual_db_path is not None:
        gameweek_kwargs[
            "db_path"
        ] = actual_db_path

    gameweek_ids = (
        _gameweek_ids(
            season_id,
            db_path=(
                actual_db_path
                if actual_db_path
                is not None
                else ensure_database()
            ),
        )
    )

    imported_at = utc_now_iso()

    from history_store import (
        DEFAULT_DB_PATH,
    )

    effective_db_path = (
        actual_db_path
        if actual_db_path is not None
        else DEFAULT_DB_PATH
    )

    with transaction(
        effective_db_path
    ) as connection:
        team_ids = _upsert_teams(
            connection,
            season_id,
            team_rows,
        )

        fixture_stats = (
            _upsert_fixtures(
                connection,
                season_id,
                fixture_rows,
                team_ids,
                gameweek_ids,
                imported_at,
            )
        )

    record_historical_import(
        season_id,
        SOURCE_REPO,
        source_ref,
        resolved_commit,
        [
            (
                f"data/{season_key}/"
                "teams.csv"
            ),
            (
                f"data/{season_key}/"
                "fixtures.csv"
            ),
        ],
        imported_at=imported_at,
        **kwargs,
    )

    return {
        "season":
            season_key,
        "resolved_commit":
            resolved_commit,
        "teams":
            len(team_ids),
        **fixture_stats,
    }


def import_historical_seasons(
    seasons=DEFAULT_SEASONS,
    source_ref=DEFAULT_SOURCE_REF,
    session=None,
    db_path=None,
):
    session = (
        session
        or requests.Session()
    )

    resolved_commit = (
        resolve_source_commit(
            source_ref,
            session=session,
        )
    )

    results = []

    for season_key in seasons:
        results.append(
            import_historical_season(
                season_key,
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
