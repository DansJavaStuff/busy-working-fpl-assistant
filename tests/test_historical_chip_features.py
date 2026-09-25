import sqlite3
import tempfile
import unittest
from pathlib import Path

from historical_chip_features import (
    historical_chip_features,
    strongest_historical_windows,
)
from history_store import (
    ensure_database,
    upsert_gameweek,
    upsert_season,
)


class HistoricalChipFeatureTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "history.db"
        ensure_database(self.db_path)

        season_id = upsert_season(
            "2025-26",
            2025,
            2026,
            db_path=self.db_path,
        )
        gw1 = upsert_gameweek(
            season_id,
            1,
            db_path=self.db_path,
        )
        gw2 = upsert_gameweek(
            season_id,
            2,
            db_path=self.db_path,
        )

        with sqlite3.connect(self.db_path) as connection:
            teams = [
                (1, "Alpha", "ALP", 5),
                (2, "Beta", "BET", 4),
                (3, "Gamma", "GAM", 3),
                (4, "Delta", "DEL", 2),
                (5, "Epsilon", "EPS", 1),
                (6, "Zeta", "ZET", 1),
                (7, "Eta", "ETA", 1),
                (8, "Theta", "THE", 1),
            ]

            connection.executemany(
                """
                INSERT INTO teams (
                    season_id,
                    fpl_team_id,
                    name,
                    short_name,
                    strength
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        season_id,
                        fpl_id,
                        name,
                        short_name,
                        strength,
                    )
                    for (
                        fpl_id,
                        name,
                        short_name,
                        strength,
                    )
                    in teams
                ],
            )

            db_teams = {
                row[1]: row[0]
                for row in connection.execute(
                    """
                    SELECT id, fpl_team_id
                    FROM teams
                    WHERE season_id = ?
                    """,
                    (season_id,),
                )
            }

            fixtures = [
                (1, gw1, 1, 5, 2, 4),
                (2, gw1, 1, 6, 2, 4),
                (3, gw1, 2, 3, 3, 3),
                (4, gw1, 4, 7, 2, 4),
                (5, gw2, 1, 2, 3, 3),
                (6, gw2, 3, 4, 3, 3),
                (7, gw2, 5, 6, 3, 3),
                (8, gw2, 7, 8, 3, 3),
            ]

            connection.executemany(
                """
                INSERT INTO fixtures (
                    season_id,
                    fpl_fixture_id,
                    gameweek_id,
                    home_team_id,
                    away_team_id,
                    home_difficulty,
                    away_difficulty
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        season_id,
                        fixture_id,
                        gameweek_id,
                        db_teams[home_id],
                        db_teams[away_id],
                        home_difficulty,
                        away_difficulty,
                    )
                    for (
                        fixture_id,
                        gameweek_id,
                        home_id,
                        away_id,
                        home_difficulty,
                        away_difficulty,
                    )
                    in fixtures
                ],
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_special_gameweek_features_are_derived(self):
        rows = historical_chip_features(
            "2025-26",
            db_path=self.db_path,
        )
        gw1 = next(
            row for row in rows
            if row["gameweek"] == 1
        )

        self.assertEqual(gw1["kind"], "blank_double")
        self.assertEqual(gw1["double_team_count"], 1)
        self.assertEqual(gw1["blank_team_count"], 1)
        self.assertEqual(gw1["premium_double_count"], 1)
        self.assertIn("ALP", gw1["premium_double_teams"])
        self.assertGreater(gw1["triple_captain_signal"], 0)
        self.assertGreater(gw1["bench_boost_signal"], 0)
        self.assertGreater(gw1["free_hit_signal"], 0)

    def test_normal_gameweek_has_zero_fixture_pattern_signals(self):
        rows = historical_chip_features(
            "2025-26",
            db_path=self.db_path,
        )
        gw2 = next(
            row for row in rows
            if row["gameweek"] == 2
        )

        self.assertEqual(gw2["kind"], "normal")
        self.assertEqual(gw2["free_hit_signal"], 0)
        self.assertEqual(gw2["bench_boost_signal"], 0)
        self.assertEqual(gw2["triple_captain_signal"], 0)

    def test_strongest_window_uses_requested_signal(self):
        rows = strongest_historical_windows(
            "2025-26",
            "TC",
            limit=1,
            db_path=self.db_path,
        )
        self.assertEqual(rows[0]["gameweek"], 1)


if __name__ == "__main__":
    unittest.main()
