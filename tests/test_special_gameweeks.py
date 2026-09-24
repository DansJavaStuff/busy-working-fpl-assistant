import unittest

from fixture_schedule import (
    build_fixture_calendar,
    summarise_gameweek,
)
from optimizer import project_gameweeks


def projection_player():
    return {
        "name": "Special GW Test Player",
        "position": "MID",
        "points_per_game": 4.0,
        "ep_next": 0.0,
        "minutes": 1800,
        "current_season_games": 6,
        "position_prior": 3.5,
        "historical_player": None,
        "xgi90": 0.0,
        "clean_sheets90": 0.0,
        "defensive90": 0.0,
        "saves90": 0.0,
        "goalkeeper_depth": {},
    }


def attacking_fixture(gameweek, multiplier=1.0):
    return {
        "gw": gameweek,
        "difficulty": 3,
        "attack_multiplier": multiplier,
        "defence_multiplier": multiplier,
    }


class FixtureCalendarTests(unittest.TestCase):

    def test_calendar_represents_blank_and_double_gameweeks(self):
        fixtures = [
            {
                "id": 1,
                "event": 10,
                "team_h": 1,
                "team_a": 2,
            },
            {
                "id": 2,
                "event": 10,
                "team_h": 3,
                "team_a": 1,
            },
        ]

        calendar = build_fixture_calendar(
            fixtures,
            team_ids=[1, 2, 3, 4],
            start_gameweek=10,
            end_gameweek=10,
        )

        self.assertEqual(
            len(calendar[10][1]),
            2,
        )
        self.assertEqual(
            len(calendar[10][4]),
            0,
        )

        summary = summarise_gameweek(
            calendar,
            10,
        )

        self.assertEqual(
            summary["kind"],
            "blank_double",
        )
        self.assertEqual(
            summary["double_teams"],
            [1],
        )
        self.assertEqual(
            summary["blank_teams"],
            [4],
        )


class SpecialGameweekProjectionTests(unittest.TestCase):

    def test_blank_gameweek_projects_zero(self):
        projections = project_gameweeks(
            projection_player(),
            fixtures=[],
            planning_gameweek=10,
            projection_end_gameweek=10,
        )

        self.assertEqual(
            projections[10],
            0.0,
        )
        self.assertEqual(
            projections["_debug"][
                "fixture_counts"
            ][10],
            0,
        )

    def test_double_gameweek_sums_both_fixtures(self):
        single = project_gameweeks(
            projection_player(),
            fixtures=[
                attacking_fixture(10),
            ],
            planning_gameweek=10,
            projection_end_gameweek=10,
        )

        double = project_gameweeks(
            projection_player(),
            fixtures=[
                attacking_fixture(10),
                attacking_fixture(10),
            ],
            planning_gameweek=10,
            projection_end_gameweek=10,
        )

        self.assertAlmostEqual(
            double[10],
            single[10] * 2,
        )
        self.assertEqual(
            double["_debug"][
                "fixture_counts"
            ][10],
            2,
        )

    def test_double_gameweek_sums_fixture_specific_difficulty(self):
        projections = project_gameweeks(
            projection_player(),
            fixtures=[
                attacking_fixture(
                    10,
                    multiplier=1.0,
                ),
                attacking_fixture(
                    10,
                    multiplier=0.5,
                ),
            ],
            planning_gameweek=10,
            projection_end_gameweek=10,
        )

        # Baseline is 4.0 * 0.85 = 3.4.
        self.assertAlmostEqual(
            projections[10],
            3.4 + 1.7,
        )

    def test_rearranged_fixture_scores_in_assigned_fpl_gameweek(self):
        projections = project_gameweeks(
            projection_player(),
            fixtures=[
                attacking_fixture(11),
            ],
            planning_gameweek=10,
            projection_end_gameweek=11,
        )

        self.assertEqual(
            projections[10],
            0.0,
        )
        self.assertGreater(
            projections[11],
            0.0,
        )
        self.assertEqual(
            projections["_debug"][
                "fixture_counts"
            ],
            {
                10: 0,
                11: 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
