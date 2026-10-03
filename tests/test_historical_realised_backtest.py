import unittest
from unittest.mock import patch

from historical_realised_backtest import (
    _captain_ownership_pool,
    _empirical_percentile,
    _fh_calibrated_players,
    _fh_archetype_summaries,
    _fh_blank_only_loso_validation,
    _fh_blank_rank_stability,
    _fh_top_week,
    _fh_extreme_diagnostics,
    _fh_model_metrics,
    _fh_outcome_detail,
    _fh_player_calibration_validation,
    _fh_player_projection_diagnostics,
    _fh_position_calibration_stats,
    _fh_projection_error_diagnostics,
    _fh_soft_monotonic_curve,
    _fh_soft_monotonic_projection,
    _fh_sensitivity_summaries,
    _prepare_predeadline_players,
    _rankdata,
    _score_fixed_squad,
    _score_predeadline_lineup,
    _solve_projected_free_hit,
    _shape_breakdown,
    _spearman,
    _tc_realised_ceiling,
    _weighted_isotonic_values,
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

    def test_small_sample_form_projection_is_regressed(self):
        result = _prepare_predeadline_players(
            [
                {
                    "fpl_element_id": 1,
                    "player_name": "Small sample",
                    "position": "MID",
                    "team_name": "Active Team",
                    "value": 50,
                    "selected": 100,
                    "season_points": 20,
                    "season_appearances": 1,
                    "recent_points": 20,
                    "recent_appearances": 1,
                    "recent_minutes": 90,
                }
            ],
            {
                "active team": {
                    "fixture_count": 1,
                    "fixture_qualities": [0.5],
                }
            },
            [],
        )
        player = result["players"][0]

        self.assertLess(
            player[
                "regressed_projection"
            ],
            player["projection"],
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

    def test_predeadline_lineup_respects_captain_pool(self):
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
                "player_name": f"P{index}",
                "position": position,
                "projection": float(index),
                "selected": 1000 - index,
                "total_points": index,
            })

        result = _score_predeadline_lineup(
            squad,
            captain_pool={"P5"},
        )

        self.assertEqual(
            result["captain"],
            "P5",
        )

    def test_captain_ownership_pool_uses_active_ownership_rank(self):
        players = [
            {
                "player_name": "Popular active",
                "selected": 100,
                "projection": 5.0,
                "fixture_rows": 1,
            },
            {
                "player_name": "Unpopular active",
                "selected": 10,
                "projection": 10.0,
                "fixture_rows": 1,
            },
            {
                "player_name": "Popular blanker",
                "selected": 1000,
                "projection": 0.0,
                "fixture_rows": 0,
            },
        ]

        self.assertEqual(
            _captain_ownership_pool(
                players,
                size=1,
            ),
            {"Popular active"},
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

    def test_projected_free_hit_breaks_captain_tie_by_ownership(self):
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )
        players = []

        for index, position in enumerate(
            positions,
            start=1,
        ):
            players.append({
                "player_name": f"P{index}",
                "position": position,
                "team_name": f"T{index}",
                "value": 50,
                "selected": index,
                "total_points": 1,
                "projection": 1.0,
            })

        players[7]["projection"] = 10.0
        players[8]["projection"] = 10.0
        players[7]["selected"] = 100
        players[8]["selected"] = 200

        result = _solve_projected_free_hit(
            players,
            captain_ownership_tiebreak=True,
        )

        self.assertEqual(
            result["captain"],
            "P9",
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

    def test_fh_model_metrics_report_bias_and_components(self):
        metrics = _fh_model_metrics(
            [
                {
                    "projected_uplift": 20.0,
                    "realised_uplift": 10.0,
                    "starter_projected_uplift": 16.0,
                    "captain_projected_uplift": 4.0,
                },
                {
                    "projected_uplift": 40.0,
                    "realised_uplift": 30.0,
                    "starter_projected_uplift": 32.0,
                    "captain_projected_uplift": 8.0,
                },
            ]
        )

        self.assertEqual(metrics["spearman"], 1.0)
        self.assertEqual(metrics["mean_error"], 10.0)
        self.assertEqual(
            metrics["mean_absolute_error"],
            10.0,
        )
        self.assertEqual(
            metrics[
                "starter_projected_mean"
            ],
            24.0,
        )
        self.assertEqual(
            metrics[
                "captain_projected_mean"
            ],
            6.0,
        )

    def test_empirical_percentile_averages_ties(self):
        self.assertEqual(
            _empirical_percentile(
                20,
                [10, 20, 20, 40],
            ),
            0.5,
        )

    def test_player_calibration_regresses_and_caps_extremes(self):
        training = [
            {
                "position": "GKP",
                "fixture_rows": 1,
                "total_points": 2,
            },
            {
                "position": "GKP",
                "fixture_rows": 1,
                "total_points": 6,
            },
        ]
        stats = _fh_position_calibration_stats(
            training
        )
        player = {
            "player_name": "Extreme keeper",
            "position": "GKP",
            "fixture_rows": 1,
            "regressed_projection": 20.0,
            "season_appearances": 10,
            "recent_minutes": 360,
        }

        position_only = _fh_calibrated_players(
            [player],
            stats,
            "position_regression",
        )[0]
        history_weighted = _fh_calibrated_players(
            [player],
            stats,
            "history_position",
        )[0]
        capped = _fh_calibrated_players(
            [player],
            stats,
            "history_position_cap",
        )[0]
        hybrid = _fh_calibrated_players(
            [player],
            stats,
            "hybrid_band_position",
            calibration_curve=[
                {
                    "projection": 0.0,
                    "calibrated": 0.0,
                },
                {
                    "projection": 10.0,
                    "calibrated": 8.0,
                },
            ],
        )[0]

        self.assertEqual(
            stats["GKP"]["prior"],
            4.0,
        )
        self.assertEqual(
            position_only["projection"],
            12.0,
        )
        self.assertEqual(
            history_weighted["projection"],
            16.0,
        )
        self.assertEqual(
            capped["projection"],
            6.0,
        )
        self.assertEqual(
            hybrid["projection"],
            13.0,
        )

    def test_weighted_isotonic_values_merge_decreasing_blocks(self):
        self.assertEqual(
            _weighted_isotonic_values(
                [1.0, 4.0, 3.0, 6.0],
                [1, 1, 1, 1],
            ),
            [1.0, 3.5, 3.5, 6.0],
        )

    def test_soft_monotonic_curve_preserves_player_order(self):
        rows = []

        for projection, actual in (
            (2.0, 2.0),
            (5.0, 5.0),
            (7.0, 3.0),
            (9.0, 8.0),
        ):
            rows.append({
                "fixture_rows": 1,
                "regressed_projection":
                    projection,
                "total_points": actual,
            })

        curve = _fh_soft_monotonic_curve(
            rows
        )
        calibrated_points = [
            point["calibrated"]
            for point in curve
        ]
        projections = [
            _fh_soft_monotonic_projection(
                value,
                curve,
            )
            for value in (
                4.0,
                6.0,
                8.0,
                10.0,
            )
        ]

        self.assertEqual(
            calibrated_points,
            sorted(calibrated_points),
        )
        self.assertEqual(
            projections,
            sorted(projections),
        )
        self.assertEqual(
            len(set(projections)),
            len(projections),
        )

    def test_player_diagnostics_expose_optimizer_selection_bias(self):
        cases = [
            {
                "season": "A",
                "gameweek": 1,
                "kind": "blank",
                "detail": {
                    "player_pool": {
                        "calibration_players": [
                            {
                                "player_name": "Selected",
                                "position": "MID",
                                "fixture_rows": 1,
                                "regressed_projection": 10.0,
                                "total_points": 1,
                                "free_hit_starter": True,
                                "template_starter": False,
                                "season_appearances": 10,
                                "recent_appearances": 5,
                            },
                            {
                                "player_name": "Rejected",
                                "position": "MID",
                                "fixture_rows": 1,
                                "regressed_projection": 3.0,
                                "total_points": 3,
                                "free_hit_starter": False,
                                "template_starter": False,
                                "season_appearances": 10,
                                "recent_appearances": 5,
                            },
                        ]
                    }
                },
            }
        ]
        diagnostics = (
            _fh_player_projection_diagnostics(
                cases
            )
        )
        roles = {
            row["key"]: row
            for row in diagnostics[
                "by_role"
            ]
        }

        self.assertEqual(
            roles["free_hit_xi"][
                "mean_error"
            ],
            9.0,
        )
        self.assertEqual(
            roles["rejected"][
                "mean_error"
            ],
            0.0,
        )

    def test_player_calibration_rebuilds_each_held_out_slate(self):
        cases = []
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )

        for season_index, season in enumerate(
            ("A", "B"),
            start=1,
        ):
            players = []

            for index, position in enumerate(
                positions,
                start=1,
            ):
                players.append({
                    "fpl_element_id":
                        season_index * 100
                        + index,
                    "player_name":
                        f"{season} P{index}",
                    "position": position,
                    "team_name":
                        f"{season} T{index}",
                    "value": 50,
                    "selected": 1000 - index,
                    "total_points": index % 6,
                    "fixture_rows": 1,
                    "projection": 3.0,
                    "regressed_projection": 3.0,
                    "season_appearances": 10,
                    "recent_appearances": 5,
                    "recent_minutes": 450,
                    "free_hit_starter":
                        index <= 11,
                    "template_starter":
                        index <= 11,
                    "template_squad": True,
                })

            players.append({
                "fpl_element_id":
                    season_index * 100
                    + 99,
                "player_name":
                    f"{season} Extreme MID",
                "position": "MID",
                "team_name":
                    f"{season} Extra",
                "value": 50,
                "selected": 1,
                "total_points": 0,
                "fixture_rows": 1,
                "projection": 12.0,
                "regressed_projection": 12.0,
                "season_appearances": 1,
                "recent_appearances": 1,
                "recent_minutes": 90,
                "free_hit_starter": True,
                "template_starter": False,
                "template_squad": False,
            })
            cases.append({
                "season": season,
                "gameweek": 1,
                "kind": "blank",
                "signal": float(
                    season_index
                ),
                "detail": {
                    "player_pool": {
                        "calibration_players":
                            players,
                    }
                },
            })

        validation = (
            _fh_player_calibration_validation(
                cases
            )
        )

        self.assertEqual(
            validation["case_count"],
            2,
        )
        self.assertEqual(
            len(validation["models"]),
            6,
        )
        self.assertTrue(
            all(
                model["case_count"] == 2
                for model in validation[
                    "models"
                ]
            )
        )
        self.assertEqual(
            validation[
                "candidate_acceptance"
            ]["candidate_key"],
            "hybrid_band_position",
        )
        self.assertEqual(
            len(
                validation[
                    "candidate_acceptance"
                ]["checks"]
            ),
            4,
        )

    def test_sensitivity_summary_pairs_baseline_on_same_cases(self):
        cases = []

        for index in range(3):
            models = []

            if index < 2:
                models.append({
                    "key": "history_floor",
                    "available": True,
                    "projected_uplift":
                        float(index + 1),
                    "realised_uplift":
                        float(index + 1),
                    "starter_projected_uplift":
                        float(index + 1),
                    "captain_projected_uplift":
                        0.0,
                })

            cases.append({
                "kind": "blank",
                "projected_uplift":
                    float(3 - index),
                "outcome":
                    float(index + 1),
                "detail": {
                    "free_hit": {
                        "starter_projected_score":
                            float(3 - index),
                        "captain_projection":
                            0.0,
                    },
                    "template": {
                        "starter_projected_score":
                            0.0,
                        "captain_projection":
                            0.0,
                    },
                    "sensitivity_models":
                        models,
                },
            })

        summaries = {
            row["key"]: row
            for row in _fh_sensitivity_summaries(
                cases
            )
        }
        history = summaries[
            "history_floor"
        ]

        self.assertEqual(
            history["overall"][
                "case_count"
            ],
            2,
        )
        self.assertEqual(
            history[
                "paired_baseline"
            ]["overall"]["case_count"],
            2,
        )
        self.assertEqual(
            history["overall"][
                "spearman"
            ],
            1.0,
        )
        self.assertEqual(
            history[
                "paired_baseline"
            ]["overall"]["spearman"],
            -1.0,
        )

    def test_blank_only_loso_blends_without_target_week_tuning(self):
        cases = []

        for season, values in (
            ("A", [10.0, 40.0]),
            ("B", [20.0, 50.0]),
            ("C", [30.0, 60.0]),
        ):
            for gameweek, value in enumerate(
                values,
                start=1,
            ):
                cases.append({
                    "season": season,
                    "gameweek": gameweek,
                    "kind": "blank",
                    "signal": value,
                    "detail": {
                        "sensitivity_models": [
                            {
                                "key": "regressed_form",
                                "available": True,
                                "projected_uplift": value,
                                "realised_uplift": value,
                            }
                        ]
                    },
                })

        cases.append({
            "season": "C",
            "gameweek": 3,
            "kind": "blank_double",
            "signal": 100.0,
            "detail": {
                "sensitivity_models": []
            },
        })
        result = (
            _fh_blank_only_loso_validation(
                cases
            )
        )

        self.assertEqual(
            result["case_count"],
            6,
        )
        self.assertGreater(
            result["combined_spearman"],
            0.9,
        )
        self.assertIn(
            "Uncalibrated",
            result[
                "mixed_blank_double_status"
            ],
        )

    def test_blank_rank_stability_holds_empty_constant_and_equal_models(self):
        self.assertEqual(_fh_blank_rank_stability([])["status"], "HOLD")
        rows = [
            {"season": season, "gameweek": gw, "signal_score": gw,
             "combined_score": gw, "realised_uplift": gw}
            for season in ("A", "B", "C") for gw in (1, 2, 3)
        ]
        self.assertEqual(_fh_blank_rank_stability(rows)["status"], "HOLD")
        for row in rows:
            row["realised_uplift"] = 0
        result = _fh_blank_rank_stability(rows)
        self.assertEqual(result["informative_seasons"], 0)
        self.assertEqual(result["status"], "HOLD")

    def test_blank_rank_stability_accepts_consistent_ranking_improvement(self):
        rows = [
            {"season": season, "gameweek": gw, "signal_score": signal,
             "combined_score": outcome, "realised_uplift": outcome}
            for season in ("A", "B", "C")
            for gw, signal, outcome in ((1, 3, 1), (2, 1, 2), (3, 2, 3))
        ]
        result = _fh_blank_rank_stability(rows)
        self.assertEqual(result["status"], "RESEARCH CANDIDATE")
        self.assertEqual(result["improved_seasons"], 3)
        self.assertEqual(result["fixture_mean_top_week_regret"], 2)
        self.assertEqual(result["blend_mean_top_week_regret"], 0)

    def test_top_week_ties_average_without_outcome_tiebreak(self):
        rows = [
            {"gameweek": 2, "signal_score": 1, "realised_uplift": -10},
            {"gameweek": 1, "signal_score": 1, "realised_uplift": 20},
        ]
        self.assertEqual(_fh_top_week(rows, "signal_score"), {
            "gameweeks": [1, 2], "realised_uplift": 5, "regret": 15,
        })

    def test_blank_rank_gate_rejects_improvement_in_only_one_season(self):
        rows = [
            {"season": season, "gameweek": gw,
             "signal_score": -gw if season == "A" else gw,
             "combined_score": gw if season == "A" else -gw,
             "realised_uplift": gw}
            for season in ("A", "B", "C") for gw in (1, 2, 3)
        ]
        result = _fh_blank_rank_stability(rows)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["improved_seasons"], 1)
        without_a = result["season_deletions"][0]
        self.assertEqual(without_a["omitted_season"], "A")
        self.assertLess(without_a["blend_delta"], 0)

    def test_loso_scores_do_not_depend_on_realised_results_or_mixed_cases(self):
        cases = [
            {"season": season, "gameweek": gw, "kind": "blank", "signal": gw,
             "detail": {"sensitivity_models": [{"key": "regressed_form",
                 "available": True, "projected_uplift": gw, "realised_uplift": gw}]}}
            for season in ("A", "B", "C") for gw in (1, 2, 3)
        ]
        with patch("historical_realised_backtest._fh_blank_rank_stability") as capture:
            _fh_blank_only_loso_validation(cases)
            before = capture.call_args.args[0]
            for case in cases:
                case["detail"]["sensitivity_models"][0]["realised_uplift"] *= -100
            cases.append({"kind": "blank_double"})
            _fh_blank_only_loso_validation(cases)
            after = capture.call_args.args[0]
        for key in ("signal_score", "projection_score", "combined_score"):
            self.assertEqual([row[key] for row in before], [row[key] for row in after])

    def test_projection_error_diagnostics_rank_overprediction(self):
        diagnostics = (
            _fh_projection_error_diagnostics(
                [
                    {
                        "season": "2024-25",
                        "gameweek": 1,
                        "kind": "blank",
                        "projected_uplift": 40.0,
                        "outcome": 5.0,
                        "detail": {
                            "free_hit": {
                                "starter_projected_score": 80.0,
                                "captain_projection": 10.0,
                            },
                            "template": {
                                "starter_projected_score": 50.0,
                                "captain_projection": 0.0,
                            },
                        },
                    },
                    {
                        "season": "2024-25",
                        "gameweek": 2,
                        "kind": "blank_double",
                        "projected_uplift": 20.0,
                        "outcome": 15.0,
                        "detail": {},
                    },
                ],
                limit=1,
            )
        )

        self.assertEqual(
            diagnostics[
                "largest_overprediction"
            ][0]["gameweek"],
            1,
        )
        self.assertEqual(
            diagnostics[
                "largest_overprediction"
            ][0]["starter_projected_uplift"],
            30.0,
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
        calibration_players = detail[
            "player_pool"
        ]["calibration_players"]
        self.assertEqual(
            len(calibration_players),
            15,
        )
        self.assertTrue(
            calibration_players[0][
                "template_squad"
            ]
        )
        self.assertTrue(
            calibration_players[-1][
                "free_hit_starter"
            ]
        )

    def test_shape_breakdown_keeps_fixture_kinds_separate(self):
        result = _shape_breakdown(
            [
                {
                    "kind": "blank",
                    "signal": 10.0,
                    "outcome": 20.0,
                },
                {
                    "kind": "blank",
                    "signal": 20.0,
                    "outcome": 30.0,
                },
                {
                    "kind": "blank_double",
                    "signal": 5.0,
                    "outcome": 80.0,
                },
                {
                    "kind": "blank_double",
                    "signal": 7.0,
                    "outcome": 70.0,
                },
            ]
        )

        by_kind = {
            row["kind"]: row
            for row in result
        }

        self.assertEqual(
            by_kind["blank"][
                "case_count"
            ],
            2,
        )
        self.assertEqual(
            by_kind["blank"][
                "spearman"
            ],
            1.0,
        )
        self.assertEqual(
            by_kind["blank_double"][
                "spearman"
            ],
            -1.0,
        )
        self.assertEqual(
            by_kind["blank_double"][
                "outcome_mean"
            ],
            75.0,
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
