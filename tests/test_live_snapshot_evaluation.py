import unittest

from live_snapshot_evaluation import (
    evaluate_live_snapshot_history,
)


def _history_item(
    gameweek,
    projected,
    actual,
    transfers=None,
    finished=True,
    bench_points=2,
    transfer_source="submitted_plan",
):
    transfers = transfers or []
    return {
        "gameweek": gameweek,
        "results": {
            "event_finished": finished,
            "projection": {
                "net": projected,
                "actual": actual,
            },
            "average_points": 50,
            "entry_history": {
                "points_on_bench":
                    bench_points,
            },
            "transfers": transfers,
            "transfer_source":
                transfer_source,
            "transfer_summary": {
                "expected_gain": 3,
                "actual_gain": 5,
                "net_actual_gain": 1,
            },
            "starters": [
                {
                    "name": "Captain",
                    "actual_points": 6,
                    "captain": True,
                },
                {
                    "name": "Best",
                    "actual_points": 10,
                    "captain": False,
                },
            ],
        },
    }


class LiveSnapshotEvaluationTests(
    unittest.TestCase
):
    def test_evaluation_summarises_completed_gameweeks(self):
        report = evaluate_live_snapshot_history([
            _history_item(
                1,
                60,
                50,
            ),
            _history_item(
                2,
                55,
                65,
                transfers=[{"in": 1}],
                bench_points=6,
            ),
        ])

        self.assertEqual(
            report["completed_gameweeks"],
            2,
        )
        self.assertFalse(
            report["ready_for_review"]
        )
        self.assertEqual(
            report[
                "projection"
            ]["mean_error"],
            0.0,
        )
        self.assertEqual(
            report[
                "projection"
            ]["mean_absolute_error"],
            10.0,
        )
        self.assertEqual(
            report[
                "transfers"
            ]["hold_gameweeks"],
            1,
        )
        self.assertEqual(
            report[
                "transfers"
            ]["net_actual_gain_mean"],
            1.0,
        )
        self.assertEqual(
            report[
                "transfers"
            ]["unmatched_execution_gameweeks"],
            0,
        )
        self.assertEqual(
            report[
                "captain"
            ]["hindsight_gap_mean"],
            4.0,
        )
        self.assertEqual(
            report[
                "lineup"
            ]["bench_points_mean"],
            4.0,
        )

    def test_evaluation_tracks_missing_and_unfinished_results(self):
        report = evaluate_live_snapshot_history([
            {
                "gameweek": 1,
                "results": None,
            },
            _history_item(
                2,
                50,
                50,
                finished=False,
            ),
        ])

        self.assertEqual(
            report[
                "missing_result_gameweeks"
            ],
            [1],
        )
        self.assertEqual(
            report[
                "unfinished_gameweeks"
            ],
            [2],
        )
        self.assertEqual(
            report["completed_gameweeks"],
            0,
        )

    def test_five_gameweeks_are_ready_for_review(self):
        report = evaluate_live_snapshot_history([
            _history_item(
                gameweek,
                50,
                50,
            )
            for gameweek in range(1, 6)
        ])

        self.assertTrue(
            report["ready_for_review"]
        )

    def test_unmatched_execution_is_not_scored_as_recommendation(self):
        report = evaluate_live_snapshot_history([
            _history_item(
                1,
                50,
                50,
                transfers=[{"in": 1}],
                transfer_source=
                    "fpl_entry_history",
            ),
        ])

        self.assertEqual(
            report[
                "transfers"
            ]["transfer_gameweeks"],
            0,
        )
        self.assertEqual(
            report[
                "transfers"
            ]["unmatched_execution_gameweeks"],
            1,
        )
        self.assertIsNone(
            report[
                "transfers"
            ]["net_actual_gain_mean"]
        )


if __name__ == "__main__":
    unittest.main()
