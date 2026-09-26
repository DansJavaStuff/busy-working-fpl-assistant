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