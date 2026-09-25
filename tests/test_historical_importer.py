import sqlite3
import tempfile
import unittest
from pathlib import Path

from historical_importer import (
    HistoricalImportError,
    import_historical_season,
    parse_season_key,
)
from history_store import (
    get_historical_imports,
)


TEAMS_CSV = """id,name,short_name,strength,strength_overall_home,strength_overall_away,strength_attack_home,strength_attack_away,strength_defence_home,strength_defence_away
1,Alpha,ALP,3,1200,1190,1210,1180,1205,1175
2,Beta,BET,2,1100,1090,1110,1080,1105,1075
3,Gamma,GAM,3,1150,1140,1160,1130,1155,1125
4,Delta,DEL,2,1050,1040,1060,1030,1055,1025
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
        text="",
        payload=None,
    ):
        self.text = text
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


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
                text=TEAMS_CSV
            )

        if url.endswith(
            "/fixtures.csv"
        ):
            return FakeResponse(
                text=FIXTURES_CSV
            )

        raise AssertionError(
            f"Unexpected URL: {url}"
        )


class HistoricalImporterTests(
    unittest.TestCase
):

    def test_parse_season_key(self):
        self.assertEqual(
            parse_season_key(
                "2025-26"
            ),
            (2025, 2026),
        )

        with self.assertRaises(
            HistoricalImportError
        ):
            parse_season_key(
                "2025-27"
            )

    def test_imports_teams_fixtures_and_source_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = (
                Path(temp)
                / "history.db"
            )

            result = (
                import_historical_season(
                    "2025-26",
                    source_ref="master",
                    resolved_commit="abc123",
                    session=FakeSession(),
                    db_path=db_path,
                )
            )

            self.assertEqual(
                result["teams"],
                4,
            )
            self.assertEqual(
                result["fixtures"],
                4,
            )
            self.assertEqual(
                result[
                    "unassigned_fixtures"
                ],
                0,
            )

            with sqlite3.connect(
                db_path
            ) as connection:
                team_count = (
                    connection.execute(
                        "SELECT COUNT(*) "
                        "FROM teams"
                    ).fetchone()[0]
                )
                fixture_count = (
                    connection.execute(
                        "SELECT COUNT(*) "
                        "FROM fixtures"
                    ).fetchone()[0]
                )
                gameweek_count = (
                    connection.execute(
                        "SELECT COUNT(*) "
                        "FROM gameweeks"
                    ).fetchone()[0]
                )
                strength = (
                    connection.execute(
                        """
                        SELECT strength
                        FROM teams
                        WHERE fpl_team_id = 1
                        """
                    ).fetchone()[0]
                )

            self.assertEqual(
                team_count,
                4,
            )
            self.assertEqual(
                fixture_count,
                4,
            )
            self.assertEqual(
                gameweek_count,
                38,
            )
            self.assertEqual(
                strength,
                3,
            )

            imports = (
                get_historical_imports(
                    db_path=db_path
                )
            )

            self.assertEqual(
                len(imports),
                1,
            )
            self.assertEqual(
                imports[0][
                    "resolved_commit"
                ],
                "abc123",
            )
            self.assertIn(
                "data/2025-26/"
                "fixtures.csv",
                imports[0]["files"],
            )


if __name__ == "__main__":
    unittest.main()
