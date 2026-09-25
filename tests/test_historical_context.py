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
TEAMS_CSV = """id,name,short_name,strength
1,Alpha,ALP,3
2,Beta,BET,2
3,Gamma,GAM,3
4,Delta,DEL,2
"""

FIXTURES_CSV = """id,event,team_h,team_a,team_h_score,team_a_score,kickoff_time,finished,team_h_difficulty,team_a_difficulty
10,1,1,2,2,0,2025-08-16T14:00:00Z,True,2,4
11,1,3,1,1,1,2025-08-17T14:00:00Z,True,3,3
12,2,1,4,2,1,2025-08-23T14:00:00Z,True,2,4
13,2,2,3,0,0,2025-08-24T14:00:00Z,True,3,3
"""


class FakeResponse:

    def __init__(
        self,
        text,
    ):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:

    def get(
        self,
        url,
        timeout=None,
        headers=None,
    ):
        del timeout, headers

        if url.endswith(
            "/teams.csv"
        ):
            return FakeResponse(
                TEAMS_CSV
            )

        if url.endswith(
            "/fixtures.csv"
        ):
            return FakeResponse(
                FIXTURES_CSV
            )

        raise AssertionError(
            f"Unexpected URL: {url}"
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
