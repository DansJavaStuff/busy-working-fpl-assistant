import unittest
from unittest.mock import patch

from chip_planner import (
    FIRST_HALF_END_GW,
    SECOND_HALF_START_GW,
    build_chip_opportunity,
    SEASON_END_GW,
    _build_timing_curve,
    _chip_boundary_status,
    _chip_cards,
    _chip_horizon_end,
    _chip_opportunity_summary,
    _chip_recommendation,
    _coordinated_chip_schedule,
    _current_squad_lineup,
    _fixture_certainty,
    _fixed_squad_horizon_score,
    _future_team_state,
    _normalise_chip_name,
    _normalise_status,
    _players_at_gameweek,
    _wildcard_projection_horizon_end,
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



class ChipOpportunityBuildTests(unittest.TestCase):

    @patch("chip_planner.save_cached_result")
    @patch("chip_planner.get_cached_result", return_value=None)
    @patch("chip_planner.get_fixtures", return_value=[])
    @patch("chip_planner.get_bootstrap", return_value={"teams": []})
    @patch("chip_planner._chip_opportunity_summary")
    @patch("chip_planner._future_chip_windows", return_value=[])
    @patch("chip_planner._triple_captain_windows", return_value={"windows": []})
    @patch("chip_planner.load_players", return_value=[])
    @patch("chip_planner.get_my_team")
    @patch("chip_planner.get_planning_gameweek", return_value=6)
    def test_opportunity_builder_uses_extended_wildcard_projection_horizon(
        self,
        _planning_gameweek,
        get_my_team,
        load_players,
        _triple_captain_windows,
        future_chip_windows,
        chip_opportunity_summary,
        _get_bootstrap,
        _get_fixtures,
        _get_cached_result,
        _save_cached_result,
    ):
        get_my_team.return_value = {
            "picks": [],
            "transfers": {
                "bank": 0,
                "limit": 1,
                "made": 0,
            },
            "chips": [],
        }
        chip_opportunity_summary.return_value = {
            "gameweek": 6,
            "rows": [],
            "curves": [],
        }

        build_chip_opportunity()

        load_players.assert_called_once_with(
            projection_end_gameweek=23,
            long_range_regression=True,
        )

        self.assertEqual(
            future_chip_windows.call_args.args[3],
            19,
        )
        self.assertEqual(
            future_chip_windows.call_args.args[4],
            23,
        )


class ChipOpportunityCurrentTeamTests(unittest.TestCase):

    @patch("chip_planner.save_cached_result")
    @patch("chip_planner.get_cached_result", return_value=None)
    @patch("chip_planner.get_fixtures", return_value=[])
    @patch("chip_planner.get_bootstrap", return_value={"teams": []})
    @patch("chip_planner._chip_opportunity_summary")
    @patch("chip_planner._future_chip_windows", return_value=[])
    @patch("chip_planner._triple_captain_windows", return_value={"windows": []})
    @patch("chip_planner.load_players", return_value=[])
    @patch("chip_planner.get_my_team")
    @patch("chip_planner.get_planning_gameweek", return_value=6)
    def test_standalone_opportunity_passes_current_team_to_scheduler(
        self,
        _planning_gameweek,
        get_my_team,
        _load_players,
        _triple_captain_windows,
        _future_chip_windows,
        chip_opportunity_summary,
        _get_bootstrap,
        _get_fixtures,
        _get_cached_result,
        _save_cached_result,
    ):
        current_team = {
            "picks": [],
            "transfers": {
                "bank": 0,
                "limit": 1,
                "made": 0,
            },
            "chips": [
                {
                    "name": "bench_boost",
                    "number": 1,
                    "status_for_entry": "available",
                    "start_event": 1,
                    "stop_event": 19,
                }
            ],
        }
        get_my_team.return_value = current_team
        chip_opportunity_summary.return_value = {
            "gameweek": 6,
            "rows": [],
            "curves": [],
            "schedule": {
                "items": [],
            },
        }

        build_chip_opportunity()

        self.assertIs(
            chip_opportunity_summary.call_args.kwargs["current_team"],
            current_team,
        )


class ChipFastLineupTests(unittest.TestCase):

    def test_current_squad_lineup_picks_valid_best_xi_without_solver(self):
        players = []
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )

        for player_id, position in enumerate(
            positions,
            start=1,
        ):
            projection = float(
                player_id
            )
            players.append({
                "id": player_id,
                "name": f"P{player_id}",
                "position": position,
                "planning_gameweek": 6,
                "proj_gw6": projection,
            })

        team = {
            "picks": [
                {
                    "element": player["id"],
                    "selling_price": 50,
                }
                for player in players
            ]
        }

        result = _current_squad_lineup(
            players,
            team,
            6,
        )

        self.assertIsNotNone(
            result
        )

        starters = [
            player
            for player in result["squad"]
            if player["starter"]
        ]

        self.assertEqual(
            len(starters),
            11,
        )
        self.assertEqual(
            sum(
                player["position"] == "GKP"
                for player in starters
            ),
            1,
        )
        self.assertGreaterEqual(
            sum(
                player["position"] == "DEF"
                for player in starters
            ),
            3,
        )
        self.assertGreaterEqual(
            sum(
                player["position"] == "MID"
                for player in starters
            ),
            2,
        )
        self.assertGreaterEqual(
            sum(
                player["position"] == "FWD"
                for player in starters
            ),
            1,
        )
        self.assertEqual(
            sum(
                bool(
                    player["captain"]
                )
                for player in starters
            ),
            1,
        )

    def test_current_squad_lineup_returns_none_for_incomplete_squad(self):
        result = _current_squad_lineup(
            [
                {
                    "id": 1,
                    "position": "GKP",
                    "planning_gameweek": 6,
                    "proj_gw6": 5.0,
                }
            ],
            {
                "picks": [
                    {
                        "element": 1,
                        "selling_price": 50,
                    }
                ]
            },
            6,
        )

        self.assertIsNone(
            result
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


class WildcardHorizonTests(unittest.TestCase):

    def test_fixed_squad_horizon_scores_five_gameweeks(self):
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )
        players = []

        for player_id, position in enumerate(
            positions,
            start=1,
        ):
            player = {
                "id": player_id,
                "name": f"P{player_id}",
                "position": position,
                "cost": 50,
            }

            for gameweek in range(
                6,
                11,
            ):
                player[
                    f"proj_gw{gameweek}"
                ] = float(player_id)

            players.append(
                player
            )

        result = _fixed_squad_horizon_score(
            players,
            players,
            6,
            19,
        )

        self.assertIsNotNone(
            result
        )
        self.assertEqual(
            result["gameweeks"],
            5,
        )
        self.assertEqual(
            result["end_gameweek"],
            10,
        )
        self.assertGreater(
            result["score"],
            0,
        )

    def test_first_half_wildcard_value_can_cross_into_second_half(self):
        positions = (
            ["GKP"] * 2
            + ["DEF"] * 5
            + ["MID"] * 5
            + ["FWD"] * 3
        )
        players = []

        for player_id, position in enumerate(
            positions,
            start=1,
        ):
            player = {
                "id": player_id,
                "name": f"P{player_id}",
                "position": position,
                "cost": 50,
            }

            for gameweek in range(
                18,
                23,
            ):
                player[
                    f"proj_gw{gameweek}"
                ] = 5.0

            players.append(
                player
            )

        result = _fixed_squad_horizon_score(
            players,
            players,
            18,
            22,
        )

        self.assertEqual(
            result["gameweeks"],
            5,
        )
        self.assertEqual(
            result["end_gameweek"],
            22,
        )

    def test_first_half_activation_boundary_extends_projection_horizon(self):
        self.assertEqual(
            _wildcard_projection_horizon_end(
                FIRST_HALF_END_GW
            ),
            23,
        )

        self.assertEqual(
            _wildcard_projection_horizon_end(
                SEASON_END_GW
            ),
            SEASON_END_GW,
        )


class ChipRecommendationTests(unittest.TestCase):

    def test_normal_week_holds_special_gameweek_chips(self):
        certainty = _fixture_certainty(
            6,
            6,
        )

        for short in (
            "FH",
            "BB",
            "TC",
        ):
            with self.subTest(
                short=short
            ):
                result = _chip_recommendation(
                    short,
                    10.0,
                    {
                        "kind": "normal",
                        "blank_team_count": 0,
                        "double_team_count": 0,
                    },
                    certainty,
                    None,
                )

                self.assertEqual(
                    result["recommendation"],
                    "HOLD",
                )

    def test_early_half_top_tc_window_still_holds(self):
        result = _chip_recommendation(
            "TC",
            8.9,
            {
                "kind": "normal",
                "blank_team_count": 0,
                "double_team_count": 0,
            },
            {
                "level": "high",
                "reason": "current",
            },
            None,
            {
                "rank": 1,
                "percentile": 100.0,
                "window_count": 14,
            },
        )

        self.assertEqual(
            result["recommendation"],
            "HOLD",
        )
        self.assertIn(
            "1 of 14",
            result["reason"],
        )
        self.assertIn(
            "future windows remain unresolved",
            result["reason"],
        )

    def test_late_half_exceptional_normal_tc_can_be_candidate(self):
        result = _chip_recommendation(
            "TC",
            8.9,
            {
                "kind": "normal",
                "blank_team_count": 0,
                "double_team_count": 0,
            },
            {
                "level": "high",
                "reason": "current",
            },
            None,
            {
                "rank": 1,
                "percentile": 100.0,
                "window_count": 4,
            },
        )

        self.assertEqual(
            result["recommendation"],
            "CANDIDATE",
        )
        self.assertEqual(
            result["model_confidence"],
            "medium",
        )

    def test_strong_near_term_special_pattern_becomes_candidate(self):
        result = _chip_recommendation(
            "TC",
            9.0,
            {
                "kind": "double",
                "blank_team_count": 0,
                "double_team_count": 4,
            },
            {
                "level": "medium",
                "reason": "near term",
            },
            {
                "best_similarity": 88.0,
            },
        )

        self.assertEqual(
            result["recommendation"],
            "CANDIDATE",
        )
        self.assertEqual(
            result["model_confidence"],
            "medium",
        )

    def test_long_range_special_pattern_still_holds(self):
        result = _chip_recommendation(
            "FH",
            12.0,
            {
                "kind": "blank",
                "blank_team_count": 6,
                "double_team_count": 0,
            },
            {
                "level": "low",
                "reason": "long range",
            },
            {
                "best_similarity": 95.0,
            },
        )

        self.assertEqual(
            result["recommendation"],
            "HOLD",
        )
        self.assertEqual(
            result["model_confidence"],
            "low",
        )

    def test_strong_multiweek_wildcard_window_can_be_candidate(self):
        result = _chip_recommendation(
            "WC",
            8.0,
            {
                "kind": "normal",
                "blank_team_count": 0,
                "double_team_count": 0,
            },
            {
                "level": "high",
                "reason": "current",
            },
            None,
            {
                "rank": 1,
                "percentile": 100.0,
                "window_count": 14,
            },
        )

        self.assertEqual(
            result["recommendation"],
            "CANDIDATE",
        )
        self.assertIn(
            "five-Gameweek",
            result["reason"],
        )

    def test_ordinary_multiweek_wildcard_window_holds(self):
        result = _chip_recommendation(
            "WC",
            2.0,
            {
                "kind": "normal",
                "blank_team_count": 0,
                "double_team_count": 0,
            },
            {
                "level": "high",
                "reason": "current",
            },
            None,
            {
                "rank": 6,
                "percentile": 60.0,
                "window_count": 14,
            },
        )

        self.assertEqual(
            result["recommendation"],
            "HOLD",
        )


class CoordinatedChipScheduleTests(unittest.TestCase):

    def _team_with_available_chips(self):
        return {
            "chips": [
                {
                    "name": "bench_boost",
                    "number": 1,
                    "status_for_entry": "available",
                    "start_event": 1,
                    "stop_event": 19,
                },
                {
                    "name": "triple_captain",
                    "number": 1,
                    "status_for_entry": "available",
                    "start_event": 1,
                    "stop_event": 19,
                },
                {
                    "name": "wildcard",
                    "number": 1,
                    "status_for_entry": "available",
                    "start_event": 2,
                    "stop_event": 19,
                },
                {
                    "name": "free_hit",
                    "number": 1,
                    "status_for_entry": "available",
                    "start_event": 2,
                    "stop_event": 19,
                },
            ]
        }

    def _curves_for_same_gameweek(self):
        return [
            {
                "short": short,
                "window_count": 1,
                "points": [
                    {
                        "gameweek": 6,
                        "value": value,
                        "rank": 1,
                        "percentile": 100.0,
                    }
                ],
            }
            for short, value in (
                ("BB", 8.0),
                ("TC", 9.0),
                ("WC", 12.0),
                ("FH", 10.0),
            )
        ]

    @patch("chip_planner._chip_recommendation")
    def test_schedule_never_assigns_two_chips_to_same_gameweek(
        self,
        recommendation,
    ):
        recommendation.return_value = {
            "recommendation": "CANDIDATE",
            "model_confidence": "medium",
            "reason": "Strong candidate.",
        }

        timing_windows = [
            {
                "gameweek": 6,
                "fixture_context": {
                    "kind": "blank_double",
                    "label": "special slate",
                    "blank_team_count": 4,
                    "double_team_count": 4,
                },
            }
        ]
        triple_captain = {
            "windows": [
                {
                    "gameweek": 6,
                    "fixture_context": {
                        "kind": "double",
                        "label": "double slate",
                        "blank_team_count": 0,
                        "double_team_count": 4,
                    },
                }
            ]
        }

        schedule = _coordinated_chip_schedule(
            6,
            self._team_with_available_chips(),
            self._curves_for_same_gameweek(),
            timing_windows,
            triple_captain,
        )

        self.assertEqual(
            schedule["scheduled_count"],
            1,
        )
        self.assertEqual(
            len({
                item["gameweek"]
                for item in schedule["scheduled"]
            }),
            1,
        )
        self.assertEqual(
            schedule["unscheduled_count"],
            3,
        )

    @patch("chip_planner._chip_recommendation")
    def test_schedule_can_leave_every_chip_unscheduled(
        self,
        recommendation,
    ):
        recommendation.return_value = {
            "recommendation": "HOLD",
            "model_confidence": "medium",
            "reason": "Not enough evidence.",
        }

        timing_windows = [
            {
                "gameweek": 6,
                "fixture_context": {
                    "kind": "normal",
                    "label": "normal fixture slate",
                    "blank_team_count": 0,
                    "double_team_count": 0,
                },
            }
        ]
        triple_captain = {
            "windows": [
                {
                    "gameweek": 6,
                    "fixture_context": {
                        "kind": "normal",
                        "label": "normal fixture slate",
                        "blank_team_count": 0,
                        "double_team_count": 0,
                    },
                }
            ]
        }

        schedule = _coordinated_chip_schedule(
            6,
            self._team_with_available_chips(),
            self._curves_for_same_gameweek(),
            timing_windows,
            triple_captain,
        )

        self.assertEqual(
            schedule["scheduled_count"],
            0,
        )
        self.assertEqual(
            schedule["unscheduled_count"],
            4,
        )
        self.assertTrue(
            all(
                item["status"]
                == "unscheduled"
                for item in schedule["items"]
            )
        )


class ChipCurveTests(unittest.TestCase):

    def test_curve_ranks_current_gameweek_against_remaining_windows(self):
        windows = [
            {
                "gameweek": 6,
                "fixture_context": {
                    "label": "normal fixture slate",
                    "kind": "normal",
                },
                "bb_value": 6.0,
            },
            {
                "gameweek": 7,
                "fixture_context": {
                    "label": "normal fixture slate",
                    "kind": "normal",
                },
                "bb_value": 4.0,
            },
            {
                "gameweek": 8,
                "fixture_context": {
                    "label": "2 double clubs",
                    "kind": "double",
                },
                "bb_value": 9.0,
            },
        ]

        curve = _build_timing_curve(
            "BB",
            windows,
            "bb_value",
            6,
        )

        self.assertEqual(
            curve["best_gameweek"],
            8,
        )
        self.assertEqual(
            curve["current_rank"],
            2,
        )
        self.assertEqual(
            curve["window_count"],
            3,
        )
        self.assertAlmostEqual(
            curve["current_percentile"],
            50.0,
            places=1,
        )

    def test_curve_percentile_runs_from_worst_zero_to_best_hundred(self):
        windows = [
            {
                "gameweek": 6,
                "fixture_context": {
                    "label": "normal",
                },
                "bb_value": 1.0,
            },
            {
                "gameweek": 7,
                "fixture_context": {
                    "label": "normal",
                },
                "bb_value": 2.0,
            },
            {
                "gameweek": 8,
                "fixture_context": {
                    "label": "normal",
                },
                "bb_value": 3.0,
            },
        ]

        curve = _build_timing_curve(
            "BB",
            windows,
            "bb_value",
            6,
        )

        self.assertEqual(
            curve["current_rank"],
            3,
        )
        self.assertEqual(
            curve["current_percentile"],
            0.0,
        )
        self.assertEqual(
            curve["points"][2]["percentile"],
            100.0,
        )

    def test_curve_marks_current_and_best_points(self):
        windows = [
            {
                "gameweek": 6,
                "fixture_context": {
                    "label": "normal",
                },
                "fh_value": 12.0,
            },
            {
                "gameweek": 7,
                "fixture_context": {
                    "label": "blank",
                },
                "fh_value": 15.0,
            },
        ]

        curve = _build_timing_curve(
            "FH",
            windows,
            "fh_value",
            6,
        )

        self.assertTrue(
            curve["points"][0]["current"]
        )
        self.assertFalse(
            curve["points"][0]["best"]
        )
        self.assertTrue(
            curve["points"][1]["best"]
        )
        self.assertEqual(
            curve["points"][1]["bar_height"],
            100.0,
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
