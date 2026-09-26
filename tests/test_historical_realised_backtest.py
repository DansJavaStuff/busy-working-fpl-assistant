import unittest
from unittest.mock import patch

from historical_realised_backtest import (
    _rankdata,
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

    def test_tc_ceiling_uses_highest_actual_scorer(self):
        result = _tc_realised_ceiling(
            [
                {
                    "player_name": "A",
                    "total_points": 12,
                    "minutes": 90,
                },
                {
                    "player_name": "B",
                    "total_points": 18,
                    "minutes": 90,
                },
                {
                    "player_name": "C",
                    "total_points": 20,
                    "minutes": 0,
                },
            ]
        )

        self.assertEqual(
            result["score"],
            18,
        )
        self.assertEqual(
            result["player"],
            "B",
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
