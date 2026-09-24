import sqlite3
import tempfile
import unittest
from pathlib import Path

from history_store import (
    current_schema_version,
    database_status,
    ensure_database,
    save_chip_opportunity,
    save_chip_outcome,
    save_snapshot,
    upsert_gameweek,
    upsert_season,
)


class HistoryStoreTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )
        self.db_path = (
            Path(self.tempdir.name)
            / "history.db"
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_database_is_created_and_migrated(self):
        path = ensure_database(
            self.db_path
        )

        self.assertTrue(
            path.exists()
        )
        self.assertEqual(
            current_schema_version(
                self.db_path
            ),
            1,
        )

        status = database_status(
            self.db_path
        )

        self.assertTrue(
            status["exists"]
        )
        self.assertEqual(
            status["schema_version"],
            1,
        )

    def test_migrations_are_idempotent(self):
        ensure_database(
            self.db_path
        )
        ensure_database(
            self.db_path
        )

        with sqlite3.connect(
            self.db_path
        ) as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM schema_migrations
                """
            ).fetchone()[0]

        self.assertEqual(
            count,
            1,
        )

    def test_can_store_core_historical_records(self):
        ensure_database(
            self.db_path
        )

        season_id = upsert_season(
            "2026-27",
            2026,
            2027,
            db_path=self.db_path,
        )

        gameweek_id = upsert_gameweek(
            season_id,
            6,
            deadline_time=
                "2026-09-26T11:00:00+00:00",
            db_path=self.db_path,
        )

        snapshot_id = save_snapshot(
            season_id,
            gameweek_id,
            "pre_deadline_fpl",
            {
                "example": True,
            },
            entry_id=5710014,
            db_path=self.db_path,
        )

        opportunity_id = (
            save_chip_opportunity(
                season_id,
                gameweek_id,
                "3xc",
                8.9,
                "hold",
                "low",
                "medium",
                payload={
                    "best_later_gw":
                        16,
                },
                db_path=self.db_path,
            )
        )

        outcome_id = save_chip_outcome(
            season_id,
            gameweek_id,
            "3xc",
            actual_value=10.0,
            entry_id=5710014,
            benchmark_value=7.0,
            incremental_value=3.0,
            db_path=self.db_path,
        )

        self.assertGreater(
            snapshot_id,
            0,
        )
        self.assertGreater(
            opportunity_id,
            0,
        )
        self.assertGreater(
            outcome_id,
            0,
        )

        with sqlite3.connect(
            self.db_path
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) "
                    "FROM seasons"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) "
                    "FROM gameweeks"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) "
                    "FROM snapshots"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) "
                    "FROM chip_opportunities"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) "
                    "FROM chip_outcomes"
                ).fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main()
