import tempfile
import unittest
from pathlib import Path

from historical_context import (
    historical_gameweek_context,
    historical_special_gameweeks,
)
from historical_importer import (
    import_historical_season,
)
from test_historical_importer import (
    FakeSession,
)


class HistoricalContextTests(
    unittest.TestCase
):

    def test_identifies_historical_blank_and_double_teams(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = (
                Path(temp)
                / "history.db"
            )

            import_historical_season(
                "2025-26",
                resolved_commit="abc123",
                session=FakeSession(),
                db_path=db_path,
            )

            context = (
                historical_gameweek_context(
                    "2025-26",
                    db_path=db_path,
                )
            )

            gw1 = next(
                row
                for row in context
                if row["gameweek"] == 1
            )

            self.assertEqual(
                gw1["kind"],
                "blank_double",
            )
            self.assertEqual(
                gw1[
                    "double_team_count"
                ],
                1,
            )
            self.assertEqual(
                gw1[
                    "blank_team_count"
                ],
                1,
            )
            self.assertIn(
                "ALP",
                gw1["double_teams"],
            )
            self.assertIn(
                "DEL",
                gw1["blank_teams"],
            )

            gw2 = next(
                row
                for row in context
                if row["gameweek"] == 2
            )

            self.assertEqual(
                gw2["kind"],
                "normal",
            )

            special = (
                historical_special_gameweeks(
                    "2025-26",
                    db_path=db_path,
                )
            )

            self.assertEqual(
                special[0]["gameweek"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
