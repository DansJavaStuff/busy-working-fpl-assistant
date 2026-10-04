"""Print historical source metadata without modifying the runtime database."""

import argparse
import json
from pathlib import Path
import sqlite3


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data/runtime/fpl_history.db"


def historical_input_provenance(db_path=DEFAULT_DB_PATH):
    # Do not use history_store.connect/ensure_database: an audit must not
    # create a missing database or apply migrations before reading evidence.
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        imports = []
        for row in connection.execute("""
            SELECT s.season_key, h.source_repo, h.requested_ref,
                   h.resolved_commit, h.imported_at, h.files_json
            FROM historical_imports h JOIN seasons s ON s.id = h.season_id
            ORDER BY s.season_key, h.imported_at, h.id
        """):
            item = dict(row)
            item["files"] = json.loads(item.pop("files_json"))
            imports.append(item)
        seasons = [dict(row) for row in connection.execute("""
            SELECT s.season_key,
              (SELECT COUNT(*) FROM gameweeks g WHERE g.season_id = s.id)
                AS gameweeks,
              (SELECT COUNT(*) FROM gameweeks g WHERE g.season_id = s.id
                AND g.deadline_time IS NOT NULL AND g.deadline_time != '')
                AS gameweeks_with_deadline,
              (SELECT COUNT(*) FROM fixtures f WHERE f.season_id = s.id)
                AS fixtures
            FROM seasons s ORDER BY s.season_key
        """)]
        cases = [dict(row) for row in connection.execute("""
            SELECT s.season_key, f.fpl_fixture_id, g.gameweek,
                   g.deadline_time, f.kickoff_time, f.home_difficulty,
                   f.away_difficulty, f.source_updated_at
            FROM fixtures f JOIN seasons s ON s.id = f.season_id
            LEFT JOIN gameweeks g ON g.id = f.gameweek_id
            WHERE (s.season_key = '2023-24' AND f.fpl_fixture_id = 162)
               OR (s.season_key = '2024-25' AND f.fpl_fixture_id = 144)
            ORDER BY s.season_key
        """)]
        return {
            "lookahead_safe": False,
            "note": "Import timestamps are not historical capture timestamps. "
                    "Import log entries do not prove which revision every row uses "
                    "after overlapping imports. See docs/historical_input_audit.md.",
            "imports": imports,
            "seasons": seasons,
            "fixture_cases": cases,
        }
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    try:
        result = historical_input_provenance(args.db)
    except (sqlite3.Error, ValueError) as exc:
        parser.exit(1, f"Cannot read historical provenance: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
