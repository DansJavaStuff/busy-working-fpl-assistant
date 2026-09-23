import unittest

from chip_planner import (
    FIRST_HALF_END_GW,
    _chip_cards,
    _future_team_state,
    _normalise_chip_name,
    _normalise_status,
    _players_at_gameweek,
)


class ChipNormalisationTests(unittest.TestCase):

    def test_chip_name_aliases_match_fpl_names(self):
        self.assertEqual(
            _normalise_chip_name({"name": "bench_boost"}),
            "bboost",
        )
        self.assertEqual(
            _normalise_chip_name({"name": "triple_captain"}),
            "3xc",
        )
        self.assertEqual(
            _normalise_chip_name({"name": "free_hit"}),
            "freehit",
        )
        self.assertEqual(
            _normalise_chip_name({"name": "wc"}),
            "wildcard",
        )

    def test_status_is_normalised_for_available_and_used_chips(self):
        self.assertEqual(
            _normalise_status({"status_for_entry": "available"}),
            "available",
        )
        self.assertEqual(
            _normalise_status({"status_for_entry": "played"}),
            "used",
        )
        self.assertEqual(
            _normalise_status({"status": "unavailable"}),
            "used",
        )

    def test_chip_cards_preserve_fpl_set_and_event_boundaries(self):
        team = {
            "chips": [
                {
                    "name": "free_hit",
                    "number": 1,
                    "status_for_entry": "available",
                    "start_event": 2,
                    "stop_event": 19,
                    "played_by_entry": None,
                },
                {
                    "name": "wildcard",
                    "number": 2,
                    "status_for_entry": "available",
                    "start_event": 20,
                    "stop_event": 38,
                    "played_by_entry": None,
                },
            ]
        }

        cards = _chip_cards(team)

        self.assertEqual(cards[0]["name"], "freehit")
        self.assertEqual(cards[0]["number"], 1)
        self.assertEqual(cards[0]["start_event"], 2)
        self.assertEqual(cards[0]["stop_event"], 19)

        self.assertEqual(cards[1]["name"], "wildcard")
        self.assertEqual(cards[1]["number"], 2)
        self.assertEqual(cards[1]["start_event"], 20)
        self.assertEqual(cards[1]["stop_event"], 38)


class ChipTimingTests(unittest.TestCase):

    def test_first_half_horizon_ends_at_gameweek_19(self):
        self.assertEqual(FIRST_HALF_END_GW, 19)

    def test_future_projection_is_clipped_at_first_half_boundary(self):
        player = {
            "name": "Example",
            "proj_gw18": 2.0,
            "proj_gw19": 3.0,
            "proj_gw20": 100.0,
            "proj_gw21": 100.0,
        }

        anchored = _players_at_gameweek(
            [player],
            18,
        )[0]

        self.assertEqual(
            anchored["proj_next"],
            2.0,
        )
        self.assertEqual(
            anchored["proj_5gw"],
            5.0,
        )

    def test_future_team_state_uses_neutral_one_free_transfer(self):
        current_team = {
            "picks": [
                {
                    "element": 1,
                    "selling_price": 50,
                }
            ],
            "transfers": {
                "limit": 4,
                "made": 2,
                "bank": 15,
            },
        }

        future = _future_team_state(
            current_team
        )

        self.assertEqual(
            future["transfers"]["limit"],
            1,
        )
        self.assertEqual(
            future["transfers"]["made"],
            0,
        )
        self.assertEqual(
            future["transfers"]["bank"],
            15,
        )

        # The timing snapshot must not mutate the authenticated
        # current-team payload that was passed in.
        self.assertEqual(
            current_team["transfers"]["limit"],
            4,
        )
        self.assertEqual(
            current_team["transfers"]["made"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
