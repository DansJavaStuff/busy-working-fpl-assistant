import unittest
from unittest.mock import patch

from historical_realised_backtest import (
    _fh_archetype_summaries,
    _fh_extreme_diagnostics,
    _fh_outcome_detail,
    _prepare_predeadline_players,
    _rankdata,
    _score_fixed_squad,
    _score_predeadline_lineup,
    _solve_projected_free_hit,
    _spearman,
    _tc_realised_ceiling,
    backtest_historical_chip_outcomes,
)


class HistoricalRealisedBacktestTests(
    unittest.TestCase
):

    def test_rankdata_uses_average_rank_for_ties(self):
        self.assertEqual(
            _rankdata(
                [10, 20, 20, 40]
            ),
            [
                1.0,
                2.5,
                2.5,
                4.0,
            ],
        )

    def test_spearman_detects_monotonic_relationship(self):
        self.assertEqual(
            _spearman(
                [1, 2, 3, 4],
                [10, 20, 30, 40],
            ),
            1.0,
        )
        self.assertEqual(
            _spearman(
                [1, 2, 3, 4],
                [40, 30, 20, 10],
            ),
            -1.0,
        )

    def test_tc_ceiling_uses_most_owned_captainable_pool(self):
        rows = []

        for index in range(
            1,
            23,
        ):
            rows.append({
                "player_name":
                    f"P{index}",
                "total_points":
                    (
                        30
                        if index == 22
                        else index
                    ),
                "minutes":
                    90,
                "selected":
                    1000 - index,
                "value":
                    100,
            })

        result = _tc_realised_ceiling(
            rows
        )

        self.assertEqual(
            result["score"],
            20,
        )
        self.assertEqual(
            result["player"],
            "P20",
        )
        self.assertEqual(
            result["pool_size"],
            20,
        )

    def test_score_fixed_squad_uses_best_valid_xi_and_captain(self):
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )
        squad = []

        for index, position in enumerate(
            positions,
            start=1,
        ):
            squad.append({
                "player_name":
                    f"P{index}",
                "position":
                    position,
                "total_points":
                    index,
            })

        result = _score_fixed_squad(
            squad
        )

        self.assertIsNotNone(
            result
        )
        self.assertEqual(
            result["captain_points"],
            15,
        )
        self.assertGreater(
            result["score"],
            result["starter_points"],
        )
        self.assertEqual(
            len(result["starters"]),
            11,
        )

    def test_fh_extreme_diagnostics_exposes_scores_and_lineups(self):
        detail = {
            "free_hit": {
                "score": 150,
                "captain": "FH captain",
            },
            "template": {
                "score": 50,
                "captain": "Template captain",
            },
            "free_hit_xi": {
                "player_fixtures": 15,
                "players": [],
            },
            "template_xi": {
                "player_fixtures": 11,
                "players": [],
            },
            "player_pool": {
                "eligible_players": 250,
                "zero_fixture_players": 0,
                "can_measure_template_blankers": False,
            },
        }
        diagnostics = (
            _fh_extreme_diagnostics(
                [
                    {
                        "season": "2023-24",
                        "gameweek": 34,
                        "kind": "blank_double",
                        "signal": 9.1,
                        "outcome": 100.0,
                        "detail": detail,
                    }
                ]
            )
        )

        self.assertEqual(
            diagnostics[0][
                "template_score"
            ],
            50,
        )
        self.assertEqual(
            diagnostics[0][
                "free_hit_score"
            ],
            150,
        )
        self.assertFalse(
            diagnostics[0][
                "player_pool"
            ][
                "can_measure_template_blankers"
            ]
        )

    def test_predeadline_pool_keeps_blankers_and_scores_them_zero(self):
        history = [
            {
                "fpl_element_id": 1,
                "player_name": "Blanker",
                "position": "MID",
                "team_name": "Blank Team",
                "value": 80,
                "selected": 1000,
                "season_points": 60,
                "season_appearances": 10,
                "recent_points": 30,
                "recent_appearances": 5,
                "recent_minutes": 450,
            },
            {
                "fpl_element_id": 2,
                "player_name": "Active",
                "position": "MID",
                "team_name": "Active Team",
                "value": 75,
                "selected": 500,
                "season_points": 50,
                "season_appearances": 10,
                "recent_points": 25,
                "recent_appearances": 5,
                "recent_minutes": 450,
            },
        ]
        fixtures = {
            "blank team": {
                "fixture_count": 0,
                "fixture_qualities": [],
            },
            "active team": {
                "fixture_count": 1,
                "fixture_qualities": [0.5],
            },
        }
        result = _prepare_predeadline_players(
            history,
            fixtures,
            [
                {
                    "fpl_element_id": 2,
                    "total_points": 8,
                    "minutes": 90,
                }
            ],
        )
        by_name = {
            row["player_name"]: row
            for row in result[
                "players"
            ]
        }

        self.assertEqual(
            by_name["Blanker"][
                "fixture_rows"
            ],
            0,
        )
        self.assertEqual(
            by_name["Blanker"][
                "total_points"
            ],
            0,
        )
        self.assertEqual(
            by_name["Blanker"][
                "projection"
            ],
            0.0,
        )
        self.assertEqual(
            by_name["Active"][
                "total_points"
            ],
            8,
        )
        self.assertGreater(
            by_name["Active"][
                "projection"
            ],
            0.0,
        )

    def test_predeadline_lineup_does_not_use_target_points(self):
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )
        squad = []

        for index, position in enumerate(
            positions,
            start=1,
        ):
            squad.append({
                "player_name":
                    f"P{index}",
                "position":
                    position,
                "projection":
                    float(
                        20 - index
                    ),
                "selected":
                    1000 - index,
                "total_points":
                    1,
            })

        squad[1][
            "total_points"
        ] = 50
        result = _score_predeadline_lineup(
            squad
        )
        starter_names = {
            player["player_name"]
            for player in result[
                "starters"
            ]
        }

        self.assertNotIn(
            "P2",
            starter_names,
        )
        self.assertEqual(
            result["captain"],
            "P1",
        )

    def test_projected_free_hit_ignores_target_week_explosion(self):
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 6
            + ["FWD"] * 3
        )
        players = []

        for index, position in enumerate(
            positions,
            start=1,
        ):
            players.append({
                "player_name":
                    f"P{index}",
                "position":
                    position,
                "team_name":
                    f"T{index}",
                "value":
                    50,
                "selected":
                    1000 - index,
                "total_points":
                    1,
                "projection":
                    float(
                        20 - index
                    ),
            })

        explosive = players[12]
        explosive["projection"] = 0.1
        explosive["total_points"] = 50
        result = _solve_projected_free_hit(
            players
        )
        starter_names = {
            player["player_name"]
            for player in result[
                "starters"
            ]
        }

        self.assertNotIn(
            explosive["player_name"],
            starter_names,
        )
        self.assertNotEqual(
            result["captain"],
            explosive["player_name"],
        )

    def test_fh_archetypes_are_summarised_separately(self):
        summaries = _fh_archetype_summaries(
            [
                {
                    "kind": "blank",
                    "signal": 10.0,
                    "outcome": 20.0,
                    "projected_uplift": 2.0,
                },
                {
                    "kind": "blank",
                    "signal": 20.0,
                    "outcome": 30.0,
                    "projected_uplift": 4.0,
                },
                {
                    "kind": "blank_double",
                    "signal": 5.0,
                    "outcome": 40.0,
                    "projected_uplift": 8.0,
                },
                {
                    "kind": "blank_double",
                    "signal": 15.0,
                    "outcome": 25.0,
                    "projected_uplift": 3.0,
                },
            ]
        )

        by_key = {
            row["key"]: row
            for row in summaries
        }

        self.assertEqual(
            by_key["blank_only"][
                "case_count"
            ],
            2,
        )
        self.assertEqual(
            by_key["blank_only"][
                "spearman"
            ],
            1.0,
        )
        self.assertEqual(
            by_key["blank_double"][
                "case_count"
            ],
            2,
        )
        self.assertEqual(
            by_key["blank_double"][
                "spearman"
            ],
            -1.0,
        )
        self.assertEqual(
            by_key["blank_only"][
                "projected_spearman"
            ],
            1.0,
        )
        self.assertEqual(
            by_key["blank_double"][
                "projected_spearman"
            ],
            1.0,
        )

    def test_fh_detail_exposes_captain_and_sample_sanity(self):
        players = []
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )

        for index, position in enumerate(
            positions,
            start=1,
        ):
            players.append({
                "player_name": f"P{index}",
                "position": position,
                "team_name": f"T{index}",
                "value": 50,
                "selected": 1000 - index,
                "total_points": index,
                "fixture_rows": 1,
                "projection": float(index),
                "season_appearances": 10,
                "recent_appearances": 5,
                "recent_minutes": 450,
            })

        players[-1]["season_appearances"] = 2
        outcome = {
            "score": 100,
            "captain": "P15",
            "projected_score": 90.0,
            "starters": players[4:],
            "squad": players,
        }
        baseline = {
            "score": 80,
            "captain": "P1",
            "projected_score": 70.0,
            "starters": players[:11],
            "squad": players,
        }
        detail = _fh_outcome_detail(
            outcome,
            baseline,
            players,
        )

        self.assertEqual(
            detail["captain_sanity"]["template"][
                "ownership_rank"
            ],
            1,
        )
        self.assertEqual(
            detail["captain_sanity"]["free_hit"][
                "ownership_rank"
            ],
            15,
        )
        self.assertEqual(
            detail["free_hit_xi"][
                "small_sample_players"
            ],
            ["P15"],
        )

    @patch(
        "historical_realised_backtest."
        "_outcome_for_chip"
    )
    @patch(
        "historical_realised_backtest."
        "load_historical_player_gameweek"
    )
    @patch(
        "historical_realised_backtest."
        "historical_chip_features"
    )
    def test_backtest_reports_and_excludes_unplayable_fh_slates(
        self,
        historical_chip_features,
        load_historical_player_gameweek,
        outcome_for_chip,
    ):
        historical_chip_features.return_value = [
            {
                "season": "2022-23",
                "gameweek": 7,
                "kind": "blank",
                "free_hit_signal": 100.0,
                "bench_boost_signal": 0.0,
                "triple_captain_signal": 0.0,
                "active_team_count": 0,
                "scheduled_fixture_count": 0,
            }
        ]

        report = backtest_historical_chip_outcomes(
            ["2022-23"]
        )
        fh = report["chips"][0]

        self.assertEqual(fh["case_count"], 0)
        self.assertEqual(
            fh["excluded_unplayable"][0][
                "gameweek"
            ],
            7,
        )
        load_historical_player_gameweek.assert_not_called()
        outcome_for_chip.assert_not_called()

    @patch(
        "historical_realised_backtest."
        "_outcome_for_chip"
    )
    @patch(
        "historical_realised_backtest."
        "load_historical_player_gameweek"
    )
    @patch(
        "historical_realised_backtest."
        "historical_chip_features"
    )
    def test_backtest_correlates_fixture_signal_with_outcome(
        self,
        historical_chip_features,
        load_historical_player_gameweek,
        outcome_for_chip,
    ):
        def feature_side_effect(
            season,
            db_path=None,
        ):
            del db_path
            base = (
                10
                if season == "2024-25"
                else 20
            )
            return [
                {
                    "season": season,
                    "gameweek": 1,
                    "kind": "double",
                    "free_hit_signal": base,
                    "bench_boost_signal": base,
                    "triple_captain_signal": base,
                },
                {
                    "season": season,
                    "gameweek": 2,
                    "kind": "double",
                    "free_hit_signal": base + 5,
                    "bench_boost_signal": base + 5,
                    "triple_captain_signal": base + 5,
                },
            ]

        historical_chip_features.side_effect = (
            feature_side_effect
        )
        load_historical_player_gameweek.return_value = [
            {
                "player_name": "A",
                "minutes": 90,
                "total_points": 5,
            }
        ]

        counters = {
            "FH": 0,
            "BB": 0,
            "TC": 0,
        }

        def outcome_side_effect(
            chip,
            rows,
            **kwargs,
        ):
            del rows, kwargs
            counters[chip] += 1
            detail = None

            if chip == "FH":
                detail = {
                    "free_hit": {
                        "projected_score":
                            float(
                                counters[chip]
                                * 2
                            ),
                    },
                    "template": {
                        "projected_score":
                            0.0,
                    },
                }

            return {
                "metric": f"{chip.lower()}_metric",
                "value": float(
                    counters[chip]
                ),
                "detail": detail,
            }

        outcome_for_chip.side_effect = (
            outcome_side_effect
        )

        report = (
            backtest_historical_chip_outcomes(
                [
                    "2024-25",
                    "2025-26",
                ]
            )
        )

        self.assertEqual(
            len(report["chips"]),
            3,
        )
        self.assertFalse(
            report["lookahead_safe"]
        )
        self.assertTrue(
            all(
                chip["case_count"] == 4
                for chip
                in report["chips"]
            )
        )
        self.assertEqual(
            report["chips"][0][
                "projection_validation"
            ]["projected_spearman"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
