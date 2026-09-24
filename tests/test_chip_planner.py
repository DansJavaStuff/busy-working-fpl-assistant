import unittest

from chip_planner import (
    FIRST_HALF_END_GW,
    SECOND_HALF_START_GW,
    SEASON_END_GW,
    _chip_boundary_status,
    _chip_cards,
    _chip_horizon_end,
    _chip_opportunity_summary,
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
            FIRST_HALF_END_GW,
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



class ChipBoundaryTests(unittest.TestCase):

    def test_first_and_second_half_horizons_are_separate(self):
        self.assertEqual(
            _chip_horizon_end(19),
            FIRST_HALF_END_GW,
        )
        self.assertEqual(
            _chip_horizon_end(20),
            SEASON_END_GW,
        )

    def test_wildcard_and_free_hit_cannot_be_played_in_gw1(self):
        for name in (
            "wildcard",
            "freehit",
        ):
            card = {
                "name": name,
                "status": "available",
                "start_event": 1,
                "stop_event": 19,
                "played_event": None,
            }

            result = _chip_boundary_status(
                card,
                1,
                [card],
            )

            self.assertFalse(
                result["available"]
            )

    def test_second_set_is_available_from_gw20(self):
        first = {
            "name": "bboost",
            "number": 1,
            "status": "used",
            "start_event": 1,
            "stop_event": 19,
            "played_event": 7,
        }
        second = {
            "name": "bboost",
            "number": 2,
            "status": "available",
            "start_event": 20,
            "stop_event": 38,
            "played_event": None,
        }

        before = _chip_boundary_status(
            second,
            19,
            [first, second],
        )
        after = _chip_boundary_status(
            second,
            20,
            [first, second],
        )

        self.assertFalse(
            before["available"]
        )
        self.assertTrue(
            after["available"]
        )

    def test_first_half_chip_expires_after_gw19(self):
        card = {
            "name": "3xc",
            "number": 1,
            "status": "available",
            "start_event": 1,
            "stop_event": 19,
            "played_event": None,
        }

        result = _chip_boundary_status(
            card,
            20,
            [card],
        )

        self.assertFalse(
            result["available"]
        )

    def test_free_hit_cannot_be_played_in_both_gw19_and_gw20(self):
        first = {
            "name": "freehit",
            "number": 1,
            "status": "used",
            "start_event": 2,
            "stop_event": 19,
            "played_event": 19,
        }
        second = {
            "name": "freehit",
            "number": 2,
            "status": "available",
            "start_event": 20,
            "stop_event": 38,
            "played_event": None,
        }

        result = _chip_boundary_status(
            second,
            SECOND_HALF_START_GW,
            [first, second],
        )

        self.assertFalse(
            result["available"]
        )
        self.assertIn(
            "GW19 and GW20",
            result["reason"],
        )

    def test_other_chip_played_in_gameweek_blocks_another_chip(self):
        played = {
            "name": "bboost",
            "number": 1,
            "status": "used",
            "start_event": 1,
            "stop_event": 19,
            "played_event": 8,
        }
        candidate = {
            "name": "3xc",
            "number": 1,
            "status": "available",
            "start_event": 1,
            "stop_event": 19,
            "played_event": None,
        }

        result = _chip_boundary_status(
            candidate,
            8,
            [played, candidate],
        )

        self.assertFalse(
            result["available"]
        )
        self.assertIn(
            "Only one chip",
            result["reason"],
        )


class ChipOpportunityTests(unittest.TestCase):

    def test_opportunity_summary_picks_strongest_later_window(self):
        timing_windows = [
            {
                "gameweek": 6,
                "fixture_context": {
                    "label": "normal fixture slate",
                },
                "bb_value": 4.0,
                "wc_value": 3.0,
                "fh_value": 2.0,
            },
            {
                "gameweek": 7,
                "fixture_context": {
                    "label": "4 blank clubs",
                },
                "bb_value": 3.0,
                "wc_value": 2.0,
                "fh_value": 7.0,
            },
            {
                "gameweek": 8,
                "fixture_context": {
                    "label": "2 double clubs",
                },
                "bb_value": 8.0,
                "wc_value": 5.0,
                "fh_value": 4.0,
            },
        ]

        triple_captain = {
            "windows": [
                {
                    "gameweek": 6,
                    "fixture_context": {
                        "label": "normal fixture slate",
                    },
                    "best_candidate": {
                        "name": "Current Captain",
                    },
                    "best_tc_uplift": 5.0,
                },
                {
                    "gameweek": 8,
                    "fixture_context": {
                        "label": "2 double clubs",
                    },
                    "best_candidate": {
                        "name": "Double Captain",
                    },
                    "best_tc_uplift": 11.0,
                },
            ],
        }

        summary = _chip_opportunity_summary(
            6,
            None,
            triple_captain,
            None,
            None,
            timing_windows,
        )

        rows = {
            row["short"]: row
            for row in summary["rows"]
        }

        self.assertEqual(
            rows["FH"]["best_later_gw"],
            7,
        )
        self.assertEqual(
            rows["BB"]["best_later_gw"],
            8,
        )
        self.assertEqual(
            rows["TC"]["best_later_gw"],
            8,
        )
        self.assertEqual(
            rows["TC"]["cost_of_waiting"],
            -6.0,
        )
        self.assertIn(
            "current FPL schedule",
            summary["note"],
        )


if __name__ == "__main__":
    unittest.main()
