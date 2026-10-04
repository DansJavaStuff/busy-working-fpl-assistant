import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools.audit_historical_input_provenance import historical_input_provenance


class HistoricalInputProvenanceTests(unittest.TestCase):
    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.db"
            with self.assertRaises(sqlite3.OperationalError):
                historical_input_provenance(path)
            self.assertFalse(path.exists())

    def test_reports_evidence_without_migrating_or_changing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            with sqlite3.connect(path) as connection:
                connection.executescript("""
                    CREATE TABLE seasons (id INTEGER, season_key TEXT);
                    CREATE TABLE historical_imports (id INTEGER, season_id INTEGER,
                        source_repo TEXT, requested_ref TEXT, resolved_commit TEXT,
                        imported_at TEXT, files_json TEXT);
                    CREATE TABLE gameweeks (id INTEGER, season_id INTEGER,
                        gameweek INTEGER, deadline_time TEXT);
                    CREATE TABLE fixtures (season_id INTEGER, fpl_fixture_id INTEGER,
                        gameweek_id INTEGER, kickoff_time TEXT, home_difficulty INTEGER,
                        away_difficulty INTEGER, source_updated_at TEXT);
                    INSERT INTO seasons VALUES (1, '2023-24');
                    INSERT INTO gameweeks VALUES (1, 1, 28, NULL);
                    INSERT INTO fixtures VALUES (1, 162, 1, '2024-03-13T19:30:00Z',
                        2, 2, '2026-10-04T12:00:00Z');
                    CREATE TABLE unrelated_secrets (token TEXT);
                    INSERT INTO unrelated_secrets VALUES ('not-for-the-report');
                """)
                connection.execute("INSERT INTO historical_imports VALUES "
                                   "(1, 1, ?, ?, ?, ?, ?)",
                                   ('vaastav/Fantasy-Premier-League', 'master', 'abc',
                                    '2026-10-04', json.dumps(['fixtures.csv'])))
            original = path.read_bytes()
            result = historical_input_provenance(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(result['imports'][0]['resolved_commit'], 'abc')
            self.assertEqual(result['seasons'][0]['gameweeks_with_deadline'], 0)
            self.assertEqual(result['fixture_cases'][0]['gameweek'], 28)
            self.assertFalse(result['lookahead_safe'])
            self.assertNotIn('not-for-the-report', json.dumps(result))
