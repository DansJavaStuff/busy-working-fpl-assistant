import unittest
from unittest.mock import patch

from historical_realised_backtest import (
    _rankdata,
    _score_fixed_squad,
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
        ):
            del rows
            counters[chip] += 1
            return {
                "metric": f"{chip.lower()}_metric",
                "value": float(
                    counters[chip]
                ),
                "detail": None,
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


if __name__ == "__main__":
    unittest.main()
