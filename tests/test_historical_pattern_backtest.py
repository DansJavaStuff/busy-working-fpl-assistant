import unittest
from unittest.mock import patch

from historical_pattern_backtest import (
    calibrate_historical_pattern_threshold,
)


class HistoricalPatternCalibrationTests(
    unittest.TestCase
):

    @patch(
        "historical_pattern_backtest."
        "closest_historical_analogues"
    )
    @patch(
        "historical_pattern_backtest."
        "historical_chip_features"
    )
    def test_leave_one_season_out_and_threshold_coverage(
        self,
        historical_chip_features,
        closest_historical_analogues,
    ):
        historical_chip_features.side_effect = (
            lambda season, db_path=None: [
                {
                    "season": season,
                    "gameweek": 10,
                    "kind": "double",
                    "bench_boost_signal": 20.0,
                    "free_hit_signal": 0.0,
                    "triple_captain_signal": 25.0,
                }
            ]
        )

        similarities = iter(
            (
                92.0,
                78.0,
                84.0,
            )
        )

        def analogue_side_effect(
            chip,
            current_features,
            limit=1,
            seasons=None,
            db_path=None,
        ):
            similarity = next(
                similarities
            )
            return [
                {
                    "season":
                        seasons[0],
                    "gameweek":
                        20,
                    "similarity":
                        similarity,
                    "bench_boost_signal":
                        18.0,
                }
            ]

        closest_historical_analogues.side_effect = (
            analogue_side_effect
        )

        report = (
            calibrate_historical_pattern_threshold(
                "BB",
                seasons=[
                    "2022-23",
                    "2023-24",
                    "2024-25",
                ],
                thresholds=[
                    80,
                    90,
                ],
            )
        )

        self.assertEqual(
            report["case_count"],
            3,
        )
        self.assertEqual(
            report["matched_count"],
            3,
        )
        self.assertEqual(
            report["similarity_min"],
            78.0,
        )
        self.assertEqual(
            report["similarity_median"],
            84.0,
        )
        self.assertEqual(
            report["similarity_max"],
            92.0,
        )
        self.assertEqual(
            report["thresholds"][0][
                "passing"
            ],
            2,
        )
        self.assertEqual(
            report["thresholds"][0][
                "coverage"
            ],
            66.7,
        )
        self.assertEqual(
            report["thresholds"][1][
                "passing"
            ],
            1,
        )

        season_calls = [
            call.kwargs["seasons"]
            for call
            in closest_historical_analogues.call_args_list
        ]

        self.assertEqual(
            season_calls,
            [
                [
                    "2023-24",
                    "2024-25",
                ],
                [
                    "2022-23",
                    "2024-25",
                ],
                [
                    "2022-23",
                    "2023-24",
                ],
            ],
        )

    @patch(
        "historical_pattern_backtest."
        "closest_historical_analogues",
        return_value=[],
    )
    @patch(
        "historical_pattern_backtest."
        "historical_chip_features"
    )
    def test_unmatched_cases_are_reported(
        self,
        historical_chip_features,
        _closest_historical_analogues,
    ):
        historical_chip_features.return_value = [
            {
                "season": "2024-25",
                "gameweek": 30,
                "kind": "blank",
                "free_hit_signal": 20.0,
                "bench_boost_signal": 0.0,
                "triple_captain_signal": 0.0,
            }
        ]

        report = (
            calibrate_historical_pattern_threshold(
                "FH",
                seasons=[
                    "2024-25",
                    "2025-26",
                ],
            )
        )

        self.assertEqual(
            report["case_count"],
            2,
        )
        self.assertEqual(
            report["matched_count"],
            0,
        )
        self.assertEqual(
            report["unmatched_count"],
            2,
        )
        self.assertIsNone(
            report["similarity_median"]
        )


if __name__ == "__main__":
    unittest.main()
