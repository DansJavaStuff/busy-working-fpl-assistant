import unittest

from snapshot_collector import (
    checkpoint_details_for_seconds,
    checkpoint_for_seconds,
)


class SnapshotCheckpointTests(
    unittest.TestCase
):

    def test_baseline_is_used_well_before_deadline(self):
        self.assertEqual(
            checkpoint_for_seconds(
                2 * 60 * 60
            ),
            "baseline",
        )

    def test_hour_checkpoint_is_detected_near_target(self):
        self.assertEqual(
            checkpoint_for_seconds(
                59 * 60
            ),
            "t60m",
        )

    def test_15_minute_checkpoint_is_detected_near_target(self):
        self.assertEqual(
            checkpoint_for_seconds(
                14 * 60
            ),
            "t15m",
        )

    def test_10_minute_checkpoint_is_detected_near_target(self):
        self.assertEqual(
            checkpoint_for_seconds(
                9 * 60
            ),
            "t10m",
        )

    def test_5_minute_checkpoint_is_detected_near_target(self):
        self.assertEqual(
            checkpoint_for_seconds(
                4 * 60
            ),
            "t5m",
        )

    def test_late_hour_checkpoint_is_recovered(self):
        details = checkpoint_details_for_seconds(
            30 * 60
        )

        self.assertEqual(
            details["label"],
            "t60m",
        )
        self.assertFalse(
            details["on_time"]
        )
        self.assertEqual(
            details["late_by_seconds"],
            30 * 60,
        )

    def test_late_15_minute_checkpoint_is_recovered(self):
        details = checkpoint_details_for_seconds(
            11 * 60
        )

        self.assertEqual(
            details["label"],
            "t15m",
        )
        self.assertFalse(
            details["on_time"]
        )

    def test_no_checkpoint_after_deadline(self):
        self.assertIsNone(
            checkpoint_for_seconds(
                0
            )
        )


if __name__ == "__main__":
    unittest.main()
