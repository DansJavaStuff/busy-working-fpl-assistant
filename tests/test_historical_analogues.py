import sqlite3
import tempfile
import unittest
from pathlib import Path

from historical_analogues import (
    closest_historical_analogues,
    current_gameweek_features,
    historical_pattern_index,
)
from historical_chip_features import (
    strongest_historical_windows,
)
from history_store import (
    ensure_database,
    record_historical_import,
    upsert_gameweek,
    upsert_season,
)


class HistoricalAnalogueTests(
    unittest.TestCase
):

    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )
        self.db_path = (
            Path(self.tempdir.name)
            / "history.db"
        )

        ensure_database(
            self.db_path
        )

        for (
            season_key,
            start_year,
        ) in (
            ("2024-25", 2024),
            ("2025-26", 2025),
        ):
            season_id = upsert_season(
                season_key,
                start_year,
                start_year + 1,
                db_path=self.db_path,
            )

            record_historical_import(
                season_id,
                "example/source",
                "main",
                f"commit-{start_year}",
                ["teams.csv", "fixtures.csv"],
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

            with sqlite3.connect(
                self.db_path
            ) as connection:
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

                team_ids = {
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
                            fixture_id
                            + (100 * start_year),
                            gameweek_id,
                            team_ids[home_id],
                            team_ids[away_id],
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

    def test_zero_signal_rows_are_not_returned(self):
        rows = strongest_historical_windows(
            "2025-26",
            "TC",
            limit=5,
            db_path=self.db_path,
        )

        self.assertEqual(
            len(rows),
            1,
        )
        self.assertGreater(
            rows[0]["triple_captain_signal"],
            0,
        )

    def test_pattern_index_spans_imported_seasons(self):
        rows = historical_pattern_index(
            "TC",
            db_path=self.db_path,
        )

        self.assertEqual(
            {
                row["season"]
                for row in rows
            },
            {
                "2024-25",
                "2025-26",
            },
        )

    def test_normal_week_has_no_free_hit_analogue(self):
        current = {
            "blank_team_count": 0,
            "double_team_count": 0,
            "premium_blank_count": 0,
            "premium_double_count": 0,
            "mean_double_fixture_quality": 0.0,
        }

        rows = closest_historical_analogues(
            "FH",
            current,
            limit=5,
            db_path=self.db_path,
        )

        self.assertEqual(
            rows,
            [],
        )

    def test_normal_week_has_no_bb_or_tc_analogue(self):
        current = {
            "blank_team_count": 0,
            "double_team_count": 0,
            "premium_blank_count": 0,
            "premium_double_count": 0,
            "mean_double_fixture_quality": 0.0,
        }

        for chip in (
            "BB",
            "TC",
        ):
            with self.subTest(
                chip=chip
            ):
                rows = closest_historical_analogues(
                    chip,
                    current,
                    limit=5,
                    db_path=self.db_path,
                )

                self.assertEqual(
                    rows,
                    [],
                )

    def test_identical_shape_is_high_similarity(self):
        current = {
            "blank_team_count": 1,
            "double_team_count": 1,
            "premium_blank_count": 0,
            "premium_double_count": 1,
            "mean_double_fixture_quality": 0.75,
        }

        rows = closest_historical_analogues(
            "TC",
            current,
            limit=1,
            db_path=self.db_path,
        )

        self.assertGreaterEqual(
            rows[0]["similarity"],
            95.0,
        )

    def test_current_fixture_features_are_derived(self):
        bootstrap = {
            "teams": [
                {
                    "id": team_id,
                    "strength": strength,
                }
                for team_id, strength
                in (
                    (1, 5),
                    (2, 4),
                    (3, 3),
                    (4, 2),
                    (5, 1),
                    (6, 1),
                    (7, 1),
                    (8, 1),
                )
            ]
        }

        fixtures = [
            {
                "event": 10,
                "team_h": 1,
                "team_a": 5,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
            },
            {
                "event": 10,
                "team_h": 1,
                "team_a": 6,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
            },
            {
                "event": 10,
                "team_h": 2,
                "team_a": 3,
                "team_h_difficulty": 3,
                "team_a_difficulty": 3,
            },
            {
                "event": 10,
                "team_h": 4,
                "team_a": 7,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
            },
        ]

        row = current_gameweek_features(
            10,
            bootstrap=bootstrap,
            fixtures=fixtures,
        )

        self.assertEqual(
            row["kind"],
            "blank_double",
        )
        self.assertEqual(
            row["blank_team_count"],
            1,
        )
        self.assertEqual(
            row["double_team_count"],
            1,
        )
        self.assertEqual(
            row["premium_double_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
