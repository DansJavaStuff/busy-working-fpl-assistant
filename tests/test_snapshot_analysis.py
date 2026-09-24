import tempfile
import unittest
from pathlib import Path

from history_store import (
    ensure_database,
    save_snapshot,
    upsert_gameweek,
    upsert_season,
)
from snapshot_analysis import (
    analyse_gameweek_snapshots,
    compare_snapshot_payloads,
)


def _payload(
    *,
    status="a",
    chance=100,
    price=75,
    ep_next="5.0",
    fixture_event=6,
    bank=10,
):
    return {
        "bootstrap": {
            "elements": [
                {
                    "id": 1,
                    "status": status,
                    "chance_of_playing_next_round":
                        chance,
                    "now_cost": price,
                    "news": "",
                    "ep_next": ep_next,
                }
            ]
        },
        "fixtures": [
            {
                "id": 100,
                "event": fixture_event,
                "kickoff_time":
                    "2026-10-10T11:30:00Z",
                "team_h": 1,
                "team_a": 2,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
            }
        ],
        "current_team": {
            "picks": [
                {
                    "element": 1,
                    "position": 1,
                    "selling_price": 75,
                    "is_captain": True,
                    "is_vice_captain": False,
                }
            ],
            "transfers": {
                "bank": bank,
                "limit": 1,
                "made": 0,
                "cost": 0,
            },
            "chips": [],
        },
    }


class SnapshotAnalysisTests(
    unittest.TestCase
):

    def test_counts_material_changes(self):
        before = _payload()
        after = _payload(
            status="d",
            chance=75,
            price=76,
            fixture_event=7,
            bank=15,
        )

        result = compare_snapshot_payloads(
            before,
            after,
        )

        self.assertEqual(
            result["availability_changes"],
            1,
        )
        self.assertEqual(
            result["price_changes"],
            1,
        )
        self.assertEqual(
            result["fixture_changes"],
            1,
        )
        self.assertTrue(
            result["team_state_changed"]
        )
        self.assertEqual(
            result["material_changes"],
            4,
        )

    def test_projection_input_change_is_tracked_separately(self):
        result = compare_snapshot_payloads(
            _payload(),
            _payload(
                ep_next="6.2"
            ),
        )

        self.assertEqual(
            result["projection_input_changes"],
            1,
        )
        self.assertEqual(
            result["material_changes"],
            0,
        )

    def test_gameweek_analysis_orders_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = (
                Path(temp)
                / "history.db"
            )

            ensure_database(
                db_path
            )

            season_id = upsert_season(
                "2026-27",
                db_path=db_path,
            )
            gameweek_id = upsert_gameweek(
                season_id,
                6,
                db_path=db_path,
            )

            for (
                checkpoint,
                captured_at,
                payload,
            ) in (
                (
                    "t15m",
                    "2026-10-10T09:45:00+00:00",
                    _payload(
                        status="d"
                    ),
                ),
                (
                    "baseline",
                    "2026-09-24T21:31:00+00:00",
                    _payload(),
                ),
                (
                    "t60m",
                    "2026-10-10T09:00:00+00:00",
                    _payload(),
                ),
            ):
                payload["checkpoint"] = (
                    checkpoint
                )

                save_snapshot(
                    season_id,
                    gameweek_id,
                    (
                        "pre_deadline_"
                        f"{checkpoint}"
                    ),
                    payload,
                    entry_id=123,
                    captured_at=
                        captured_at,
                    db_path=db_path,
                )

            result = (
                analyse_gameweek_snapshots(
                    6,
                    123,
                    db_path=db_path,
                )
            )

            self.assertTrue(
                result["ready"]
            )
            self.assertEqual(
                result["snapshot_count"],
                3,
            )
            self.assertEqual(
                result["comparisons"][0][
                    "from_checkpoint"
                ],
                "baseline",
            )
            self.assertEqual(
                result["comparisons"][0][
                    "to_checkpoint"
                ],
                "t60m",
            )
            self.assertEqual(
                result["comparisons"][1][
                    "to_checkpoint"
                ],
                "t15m",
            )


if __name__ == "__main__":
    unittest.main()
