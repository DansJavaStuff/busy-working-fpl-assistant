import tempfile
import unittest
from pathlib import Path

from historical_outcome_importer import (
    _aggregate_rows,
    import_historical_player_outcomes,
    load_historical_player_gameweek,
)
from history_store import (
    get_historical_imports,
)


MERGED_GW_CSV = """name,position,team,element,minutes,round,starts,total_points,value,selected,GW
Alpha One,MID,Alpha,10,90,1,1,8,70,1000,1
Beta Two,FWD,Beta,20,90,1,1,5,80,900,1
Alpha One,MID,Alpha,10,85,2,1,6,70,1100,2
Alpha One,MID,Alpha,10,90,2,1,7,70,1200,2
Beta Two,FWD,Beta,20,45,2,0,2,80,950,2
"""


class FakeResponse:

    def __init__(self, text):
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
            "/gws/merged_gw.csv"
        ):
            return FakeResponse(
                MERGED_GW_CSV
            )

        raise AssertionError(
            f"Unexpected URL: {url}"
        )


class HistoricalOutcomeImporterTests(
    unittest.TestCase
):

    def test_aggregate_rows_sums_double_gameweek_player_rows(self):
        rows = [
            {
                "name": "Alpha One",
                "position": "MID",
                "team": "Alpha",
                "element": "10",
                "minutes": "85",
                "starts": "1",
                "total_points": "6",
                "value": "70",
                "selected": "1100",
                "GW": "2",
            },
            {
                "name": "Alpha One",
                "position": "MID",
                "team": "Alpha",
                "element": "10",
                "minutes": "90",
                "starts": "1",
                "total_points": "7",
                "value": "70",
                "selected": "1200",
                "GW": "2",
            },
        ]

        result = _aggregate_rows(
            rows
        )

        self.assertEqual(
            len(result),
            1,
        )
        self.assertEqual(
            result[0]["total_points"],
            13,
        )
        self.assertEqual(
            result[0]["minutes"],
            175,
        )
        self.assertEqual(
            result[0]["starts"],
            2,
        )
        self.assertEqual(
            result[0]["fixture_rows"],
            2,
        )
        self.assertEqual(
            result[0]["selected"],
            1200,
        )

    def test_import_and_load_player_gameweek_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = (
                Path(temp)
                / "history.db"
            )

            result = (
                import_historical_player_outcomes(
                    "2025-26",
                    resolved_commit="abc123",
                    session=FakeSession(),
                    db_path=db_path,
                )
            )

            self.assertEqual(
                result["rows"],
                4,
            )
            self.assertEqual(
                result["gameweeks"],
                2,
            )

            gw2 = (
                load_historical_player_gameweek(
                    "2025-26",
                    2,
                    db_path=db_path,
                )
            )

            alpha = next(
                row
                for row in gw2
                if row[
                    "fpl_element_id"
                ] == 10
            )

            self.assertEqual(
                alpha["total_points"],
                13,
            )
            self.assertEqual(
                alpha["fixture_rows"],
                2,
            )

            imports = (
                get_historical_imports(
                    db_path=db_path
                )
            )

            self.assertIn(
                "data/2025-26/gws/"
                "merged_gw.csv",
                imports[0]["files"],
            )


if __name__ == "__main__":
    unittest.main()
