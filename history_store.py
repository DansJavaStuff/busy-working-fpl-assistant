import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "runtime"
    / "fpl_history.db"
)
MIGRATIONS_DIR = (
    PROJECT_ROOT
    / "db"
    / "migrations"
)


class HistoryStoreError(RuntimeError):
    pass


def utc_now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect(
    db_path=DEFAULT_DB_PATH,
):
    db_path = Path(db_path)
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        db_path,
    )
    connection.row_factory = (
        sqlite3.Row
    )
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )
    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


@contextmanager
def transaction(
    db_path=DEFAULT_DB_PATH,
):
    connection = connect(
        db_path
    )

    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _migration_files(
    migrations_dir=MIGRATIONS_DIR,
):
    migrations_dir = Path(
        migrations_dir
    )

    return sorted(
        path
        for path in migrations_dir.glob(
            "*.sql"
        )
        if path.name[:3].isdigit()
    )


def current_schema_version(
    db_path=DEFAULT_DB_PATH,
):
    db_path = Path(db_path)

    if not db_path.exists():
        return 0

    with connect(db_path) as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'schema_migrations'
            """
        ).fetchone()

        if table is None:
            return 0

        row = connection.execute(
            """
            SELECT COALESCE(MAX(version), 0)
            AS version
            FROM schema_migrations
            """
        ).fetchone()

        return int(
            row["version"]
        )


def migrate(
    db_path=DEFAULT_DB_PATH,
    migrations_dir=MIGRATIONS_DIR,
):
    files = _migration_files(
        migrations_dir
    )

    with transaction(
        db_path
    ) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            schema_migrations (
                version INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

        applied = {
            row["version"]
            for row in connection.execute(
                """
                SELECT version
                FROM schema_migrations
                """
            )
        }

        for path in files:
            version = int(
                path.name[:3]
            )

            if version in applied:
                continue

            sql = path.read_text(
                encoding="utf-8"
            )

            connection.executescript(
                sql
            )

            connection.execute(
                """
                INSERT INTO schema_migrations (
                    version,
                    filename,
                    applied_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    version,
                    path.name,
                    utc_now_iso(),
                ),
            )

    return current_schema_version(
        db_path
    )


def ensure_database(
    db_path=DEFAULT_DB_PATH,
):
    migrate(
        db_path
    )

    return Path(
        db_path
    )


def database_status(
    db_path=DEFAULT_DB_PATH,
):
    path = Path(
        db_path
    )

    version = current_schema_version(
        path
    )

    return {
        "path":
            path,
        "exists":
            path.exists(),
        "schema_version":
            version,
    }


def _json_text(value):
    if value is None:
        return None

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    )


def upsert_season(
    season_key,
    starts_year=None,
    ends_year=None,
    source="local",
    db_path=DEFAULT_DB_PATH,
):
    with transaction(
        db_path
    ) as connection:
        connection.execute(
            """
            INSERT INTO seasons (
                season_key,
                starts_year,
                ends_year,
                source
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(season_key)
            DO UPDATE SET
                starts_year = excluded.starts_year,
                ends_year = excluded.ends_year,
                source = excluded.source
            """,
            (
                season_key,
                starts_year,
                ends_year,
                source,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM seasons
            WHERE season_key = ?
            """,
            (
                season_key,
            ),
        ).fetchone()

        return int(
            row["id"]
        )


def upsert_gameweek(
    season_id,
    gameweek,
    deadline_time=None,
    finished=None,
    data_checked=None,
    db_path=DEFAULT_DB_PATH,
):
    with transaction(
        db_path
    ) as connection:
        connection.execute(
            """
            INSERT INTO gameweeks (
                season_id,
                gameweek,
                deadline_time,
                finished,
                data_checked
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(
                season_id,
                gameweek
            )
            DO UPDATE SET
                deadline_time =
                    excluded.deadline_time,
                finished =
                    excluded.finished,
                data_checked =
                    excluded.data_checked
            """,
            (
                season_id,
                gameweek,
                deadline_time,
                (
                    None
                    if finished is None
                    else int(bool(finished))
                ),
                (
                    None
                    if data_checked is None
                    else int(bool(data_checked))
                ),
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM gameweeks
            WHERE season_id = ?
              AND gameweek = ?
            """,
            (
                season_id,
                gameweek,
            ),
        ).fetchone()

        return int(
            row["id"]
        )


def save_snapshot(
    season_id,
    gameweek_id,
    snapshot_type,
    payload,
    entry_id=None,
    captured_at=None,
    source="official_fpl",
    db_path=DEFAULT_DB_PATH,
):
    captured_at = (
        captured_at
        or utc_now_iso()
    )

    with transaction(
        db_path
    ) as connection:
        cursor = connection.execute(
            """
            INSERT INTO snapshots (
                season_id,
                gameweek_id,
                entry_id,
                snapshot_type,
                captured_at,
                source,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season_id,
                gameweek_id,
                entry_id,
                snapshot_type,
                captured_at,
                source,
                _json_text(
                    payload
                ),
            ),
        )

        return int(
            cursor.lastrowid
        )


def save_chip_opportunity(
    season_id,
    gameweek_id,
    chip_name,
    projected_value,
    recommendation,
    fixture_certainty,
    model_confidence,
    payload=None,
    model_version=None,
    created_at=None,
    db_path=DEFAULT_DB_PATH,
):
    created_at = (
        created_at
        or utc_now_iso()
    )

    with transaction(
        db_path
    ) as connection:
        cursor = connection.execute(
            """
            INSERT INTO chip_opportunities (
                season_id,
                gameweek_id,
                chip_name,
                projected_value,
                recommendation,
                fixture_certainty,
                model_confidence,
                model_version,
                created_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season_id,
                gameweek_id,
                chip_name,
                projected_value,
                recommendation,
                fixture_certainty,
                model_confidence,
                model_version,
                created_at,
                _json_text(
                    payload
                ),
            ),
        )

        return int(
            cursor.lastrowid
        )


def save_chip_outcome(
    season_id,
    gameweek_id,
    chip_name,
    actual_value,
    entry_id=None,
    benchmark_value=None,
    incremental_value=None,
    source="derived",
    payload=None,
    created_at=None,
    db_path=DEFAULT_DB_PATH,
):
    created_at = (
        created_at
        or utc_now_iso()
    )

    with transaction(
        db_path
    ) as connection:
        cursor = connection.execute(
            """
            INSERT INTO chip_outcomes (
                season_id,
                gameweek_id,
                entry_id,
                chip_name,
                actual_value,
                benchmark_value,
                incremental_value,
                source,
                created_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season_id,
                gameweek_id,
                entry_id,
                chip_name,
                actual_value,
                benchmark_value,
                incremental_value,
                source,
                created_at,
                _json_text(
                    payload
                ),
            ),
        )

        return int(
            cursor.lastrowid
        )



def get_cached_result(
    namespace,
    cache_key,
    model_version,
    now=None,
    db_path=DEFAULT_DB_PATH,
):
    now = (
        time.time()
        if now is None
        else float(now)
    )

    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        row = connection.execute(
            """
            SELECT payload_json
            FROM derived_cache
            WHERE namespace = ?
              AND cache_key = ?
              AND model_version = ?
              AND expires_at > ?
            """,
            (
                namespace,
                cache_key,
                model_version,
                now,
            ),
        ).fetchone()

    if row is None:
        return None

    try:
        return json.loads(
            row["payload_json"]
        )
    except json.JSONDecodeError:
        return None


def save_cached_result(
    namespace,
    cache_key,
    model_version,
    payload,
    ttl_seconds,
    now=None,
    db_path=DEFAULT_DB_PATH,
):
    now = (
        time.time()
        if now is None
        else float(now)
    )
    expires_at = (
        now
        + float(ttl_seconds)
    )

    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
        connection.execute(
            """
            INSERT INTO derived_cache (
                namespace,
                cache_key,
                model_version,
                created_at,
                expires_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                namespace,
                cache_key,
                model_version
            )
            DO UPDATE SET
                created_at =
                    excluded.created_at,
                expires_at =
                    excluded.expires_at,
                payload_json =
                    excluded.payload_json
            """,
            (
                namespace,
                cache_key,
                model_version,
                now,
                expires_at,
                _json_text(
                    payload
                ),
            ),
        )


def delete_cached_result(
    namespace,
    cache_key,
    model_version,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
        cursor = connection.execute(
            """
            DELETE FROM derived_cache
            WHERE namespace = ?
              AND cache_key = ?
              AND model_version = ?
            """,
            (
                namespace,
                cache_key,
                model_version,
            ),
        )

        return cursor.rowcount


def prune_expired_cache(
    now=None,
    db_path=DEFAULT_DB_PATH,
):
    now = (
        time.time()
        if now is None
        else float(now)
    )

    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
        cursor = connection.execute(
            """
            DELETE FROM derived_cache
            WHERE expires_at <= ?
            """,
            (
                now,
            ),
        )

        return cursor.rowcount



def snapshot_exists(
    season_id,
    gameweek_id,
    snapshot_type,
    entry_id=None,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        if entry_id is None:
            row = connection.execute(
                """
                SELECT 1
                FROM snapshots
                WHERE season_id = ?
                  AND gameweek_id = ?
                  AND snapshot_type = ?
                  AND entry_id IS NULL
                LIMIT 1
                """,
                (
                    season_id,
                    gameweek_id,
                    snapshot_type,
                ),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT 1
                FROM snapshots
                WHERE season_id = ?
                  AND gameweek_id = ?
                  AND snapshot_type = ?
                  AND entry_id = ?
                LIMIT 1
                """,
                (
                    season_id,
                    gameweek_id,
                    snapshot_type,
                    int(entry_id),
                ),
            ).fetchone()

    return row is not None



def record_collector_state(
    status,
    gameweek=None,
    seconds_remaining=None,
    message=None,
    collector_name="predeadline",
    checked_at=None,
    db_path=DEFAULT_DB_PATH,
):
    checked_at = (
        checked_at
        or utc_now_iso()
    )

    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
        connection.execute(
            """
            INSERT INTO collector_state (
                collector_name,
                checked_at,
                status,
                gameweek,
                seconds_remaining,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(collector_name)
            DO UPDATE SET
                checked_at =
                    excluded.checked_at,
                status =
                    excluded.status,
                gameweek =
                    excluded.gameweek,
                seconds_remaining =
                    excluded.seconds_remaining,
                message =
                    excluded.message
            """,
            (
                collector_name,
                checked_at,
                status,
                gameweek,
                seconds_remaining,
                message,
            ),
        )


def get_collector_state(
    collector_name="predeadline",
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        row = connection.execute(
            """
            SELECT
                collector_name,
                checked_at,
                status,
                gameweek,
                seconds_remaining,
                message
            FROM collector_state
            WHERE collector_name = ?
            """,
            (
                collector_name,
            ),
        ).fetchone()

    return (
        dict(row)
        if row is not None
        else None
    )


def get_gameweek_snapshots(
    gameweek,
    entry_id,
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
                snapshots.snapshot_type,
                snapshots.captured_at,
                snapshots.payload_json
            FROM snapshots
            JOIN gameweeks
              ON gameweeks.id =
                 snapshots.gameweek_id
            WHERE gameweeks.gameweek = ?
              AND snapshots.entry_id = ?
              AND snapshots.snapshot_type
                  LIKE 'pre_deadline_%'
            ORDER BY
                snapshots.captured_at
            """,
            (
                int(gameweek),
                int(entry_id),
            ),
        ).fetchall()

    result = []

    for row in rows:
        payload = {}

        try:
            payload = json.loads(
                row["payload_json"]
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            pass

        result.append({
            "snapshot_type":
                row["snapshot_type"],
            "captured_at":
                row["captured_at"],
            "checkpoint":
                payload.get(
                    "checkpoint"
                ),
            "seconds_remaining":
                payload.get(
                    "seconds_remaining"
                ),
            "late_by_seconds":
                payload.get(
                    "late_by_seconds",
                    0,
                ),
            "on_time":
                payload.get(
                    "on_time",
                    True,
                ),
        })

    return result



def get_gameweek_snapshot_payloads(
    gameweek,
    entry_id,
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
                snapshots.snapshot_type,
                snapshots.captured_at,
                snapshots.payload_json
            FROM snapshots
            JOIN gameweeks
              ON gameweeks.id =
                 snapshots.gameweek_id
            WHERE gameweeks.gameweek = ?
              AND snapshots.entry_id = ?
              AND snapshots.snapshot_type
                  LIKE 'pre_deadline_%'
            ORDER BY
                snapshots.captured_at
            """,
            (
                int(gameweek),
                int(entry_id),
            ),
        ).fetchall()

    result = []

    for row in rows:
        try:
            payload = json.loads(
                row["payload_json"]
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            continue

        result.append({
            "snapshot_type":
                row["snapshot_type"],
            "captured_at":
                row["captured_at"],
            "checkpoint":
                payload.get(
                    "checkpoint"
                ),
            "payload":
                payload,
        })

    return result



def upsert_team(
    season_id,
    fpl_team_id,
    name,
    short_name=None,
    source="official_fpl",
    strength=None,
    strength_overall_home=None,
    strength_overall_away=None,
    strength_attack_home=None,
    strength_attack_away=None,
    strength_defence_home=None,
    strength_defence_away=None,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
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
                name,
                short_name,
                source,
                strength,
                strength_overall_home,
                strength_overall_away,
                strength_attack_home,
                strength_attack_away,
                strength_defence_home,
                strength_defence_away,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM teams
            WHERE season_id = ?
              AND fpl_team_id = ?
            """,
            (
                season_id,
                fpl_team_id,
            ),
        ).fetchone()

        return int(
            row["id"]
        )


def upsert_fixture(
    season_id,
    fpl_fixture_id,
    gameweek_id,
    home_team_id,
    away_team_id,
    kickoff_time=None,
    home_difficulty=None,
    away_difficulty=None,
    home_score=None,
    away_score=None,
    finished=None,
    source="official_fpl",
    source_updated_at=None,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
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
                fpl_fixture_id,
                gameweek_id,
                home_team_id,
                away_team_id,
                kickoff_time,
                home_difficulty,
                away_difficulty,
                home_score,
                away_score,
                (
                    None
                    if finished is None
                    else int(bool(finished))
                ),
                source,
                source_updated_at,
            ),
        )


def record_historical_import(
    season_id,
    source_repo,
    requested_ref,
    resolved_commit,
    files,
    imported_at=None,
    db_path=DEFAULT_DB_PATH,
):
    imported_at = (
        imported_at
        or utc_now_iso()
    )

    ensure_database(
        db_path
    )

    with transaction(
        db_path
    ) as connection:
        existing = connection.execute(
            """
            SELECT files_json
            FROM historical_imports
            WHERE season_id = ?
              AND source_repo = ?
              AND resolved_commit = ?
            """,
            (
                season_id,
                source_repo,
                resolved_commit,
            ),
        ).fetchone()

        merged_files = list(files)

        if existing is not None:
            try:
                merged_files.extend(
                    json.loads(
                        existing[
                            "files_json"
                        ]
                    )
                )
            except (
                TypeError,
                json.JSONDecodeError,
            ):
                pass

        merged_files = sorted(
            {
                str(path)
                for path in merged_files
            }
        )

        connection.execute(
            """
            INSERT INTO historical_imports (
                season_id,
                source_repo,
                requested_ref,
                resolved_commit,
                imported_at,
                files_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                season_id,
                source_repo,
                resolved_commit
            )
            DO UPDATE SET
                requested_ref =
                    excluded.requested_ref,
                imported_at =
                    excluded.imported_at,
                files_json =
                    excluded.files_json
            """,
            (
                season_id,
                source_repo,
                requested_ref,
                resolved_commit,
                imported_at,
                _json_text(
                    merged_files
                ),
            ),
        )


def get_historical_imports(
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
                seasons.season_key,
                historical_imports.source_repo,
                historical_imports.requested_ref,
                historical_imports.resolved_commit,
                historical_imports.imported_at,
                historical_imports.files_json
            FROM historical_imports
            JOIN seasons
              ON seasons.id =
                 historical_imports.season_id
            ORDER BY
                seasons.starts_year,
                historical_imports.imported_at
            """
        ).fetchall()

    result = []

    for row in rows:
        item = dict(row)

        try:
            item["files"] = json.loads(
                item.pop(
                    "files_json"
                )
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            item["files"] = []

        result.append(
            item
        )

    return result
