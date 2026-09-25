import sqlite3
import tempfile
import unittest
from pathlib import Path

from history_store import (
    current_schema_version,
    database_status,
    ensure_database,
    get_cached_result,
    get_collector_state,
    get_gameweek_snapshots,
    save_chip_opportunity,
    save_chip_outcome,
    save_cached_result,
    save_snapshot,
    snapshot_exists,
    record_collector_state,
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
            4,
        )

        status = database_status(
            self.db_path
        )

        self.assertTrue(
            status["exists"]
        )
        self.assertEqual(
            status["schema_version"],
            4,
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
            4,
        )

    def test_derived_cache_round_trip_and_expiry(self):
        ensure_database(
            self.db_path
        )

        save_cached_result(
            "chip_planner",
            "abc123",
            "model-v1",
            {
                "gameweek": 6,
                "value": 12.5,
            },
            ttl_seconds=60,
            now=1000,
            db_path=self.db_path,
        )

        cached = get_cached_result(
            "chip_planner",
            "abc123",
            "model-v1",
            now=1030,
            db_path=self.db_path,
        )

        self.assertEqual(
            cached,
            {
                "gameweek": 6,
                "value": 12.5,
            },
        )

        expired = get_cached_result(
            "chip_planner",
            "abc123",
            "model-v1",
            now=1061,
            db_path=self.db_path,
        )

        self.assertIsNone(
            expired
        )

    def test_derived_cache_is_model_version_specific(self):
        ensure_database(
            self.db_path
        )

        save_cached_result(
            "chip_planner",
            "same-inputs",
            "model-v1",
            {
                "value": 1,
            },
            ttl_seconds=60,
            now=1000,
            db_path=self.db_path,
        )

        self.assertIsNone(
            get_cached_result(
                "chip_planner",
                "same-inputs",
                "model-v2",
                now=1010,
                db_path=self.db_path,
            )
        )

    def test_snapshot_exists_distinguishes_checkpoint_type(self):
        ensure_database(
            self.db_path
        )

        season_id = upsert_season(
            "2026-27",
            db_path=self.db_path,
        )
        gameweek_id = upsert_gameweek(
            season_id,
            6,
            db_path=self.db_path,
        )

        save_snapshot(
            season_id,
            gameweek_id,
            "pre_deadline_baseline",
            {"ok": True},
            entry_id=123,
            db_path=self.db_path,
        )

        self.assertTrue(
            snapshot_exists(
                season_id,
                gameweek_id,
                "pre_deadline_baseline",
                entry_id=123,
                db_path=self.db_path,
            )
        )

        self.assertFalse(
            snapshot_exists(
                season_id,
                gameweek_id,
                "pre_deadline_t15m",
                entry_id=123,
                db_path=self.db_path,
            )
        )

    def test_collector_state_and_snapshot_status(self):
        ensure_database(
            self.db_path
        )

        record_collector_state(
            "not_due",
            gameweek=6,
            seconds_remaining=7200,
            message="baseline",
            checked_at=
                "2026-09-24T21:00:00+00:00",
            db_path=self.db_path,
        )

        state = get_collector_state(
            db_path=self.db_path
        )

        self.assertEqual(
            state["status"],
            "not_due",
        )
        self.assertEqual(
            state["gameweek"],
            6,
        )

        season_id = upsert_season(
            "2026-27",
            db_path=self.db_path,
        )
        gameweek_id = upsert_gameweek(
            season_id,
            6,
            db_path=self.db_path,
        )

        save_snapshot(
            season_id,
            gameweek_id,
            "pre_deadline_t15m",
            {
                "checkpoint": "t15m",
                "seconds_remaining": 720,
                "late_by_seconds": 180,
                "on_time": True,
            },
            entry_id=123,
            db_path=self.db_path,
        )

        snapshots = get_gameweek_snapshots(
            6,
            123,
            db_path=self.db_path,
        )

        self.assertEqual(
            len(snapshots),
            1,
        )
        self.assertEqual(
            snapshots[0]["checkpoint"],
            "t15m",
        )
        self.assertEqual(
            snapshots[0]["late_by_seconds"],
            180,
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
