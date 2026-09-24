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
