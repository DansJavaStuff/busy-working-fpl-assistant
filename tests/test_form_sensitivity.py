from copy import deepcopy
import unittest
from unittest.mock import patch

from form_sensitivity import (
    compare_frozen_inputs, model_signature, reweight_player, select_plan, wildcard_comparison,
)
from optimizer import calculate_captain_score, project_gameweeks
from tests.test_special_gameweeks import projection_player, attacking_fixture


def saved_player(player_id=1, minutes=450, fixtures=None):
    inputs = projection_player()
    inputs.update(id=player_id, current_season_games=5, minutes=minutes,
                  points_per_game=9.4, position_prior=4.008829339143064,
                  ep_next=10.7, xgi90=0.5)
    fixtures = fixtures if fixtures is not None else [attacking_fixture(6, 1.009827113858007)]
    projections = project_gameweeks(inputs, fixtures, 6, 10)
    player = {'id': player_id, 'name': f'Player {player_id}', 'position': 'MID',
              'planning_gameweek': 6, 'projection_input': inputs, 'fixtures': fixtures,
              'availability_factor': 0.75, 'can_select': True, 'projection_debug': projections['_debug']}
    for gw in range(6, 11):
        player[f'proj_gw{gw}'] = projections[gw] * (0.75 if gw == 6 else 1)
    return player


class FormSensitivityTests(unittest.TestCase):
    def test_control_replays_normal_blank_and_double_inputs_without_mutation(self):
        for fixtures in ([attacking_fixture(6)], [], [attacking_fixture(6), attacking_fixture(6)]):
            with self.subTest(fixtures=fixtures):
                saved = saved_player(fixtures=fixtures)
                before = deepcopy(saved)
                replay = reweight_player(saved, 6, 'control_6gw')
                for gw in range(6, 11):
                    self.assertAlmostEqual(replay[f'proj_gw{gw}'], saved[f'proj_gw{gw}'])
                self.assertEqual(saved, before)

    def test_override_keeps_default_rule_and_rejects_invalid_weights(self):
        player = projection_player()
        default = project_gameweeks(player, [attacking_fixture(6)], 6, 10)
        explicit = project_gameweeks(player, [attacking_fixture(6)], 6, 10, current_season_weight_override=1)
        self.assertEqual(default, explicit)
        for weight in (-0.1, 1.1, float('nan')):
            with self.assertRaises(ValueError):
                project_gameweeks(player, [], 6, current_season_weight_override=weight)

    def test_minutes_cap_protects_tiny_sample_and_keeps_other_inputs(self):
        saved = saved_player(minutes=90)
        capped = reweight_player(saved, 6, 'form_12gw_minutes_cap')
        self.assertAlmostEqual(capped['projection_debug']['current_season_weight'], 1/12)
        self.assertEqual(capped['projection_input']['ep_next'], 10.7)
        self.assertEqual(capped['fixtures'], saved['fixtures'])
        self.assertEqual(capped['availability_factor'], 0.75)

    def test_unselectable_players_remain_zero_across_horizon(self):
        saved = saved_player()
        saved['can_select'] = False
        adjusted = reweight_player(saved, 6, 'form_12gw')
        self.assertEqual(adjusted['proj_5gw'], 0)

    def test_63_minute_high_ppg_doubt_is_shrunk_without_changing_availability(self):
        saved = saved_player(minutes=63, fixtures=[attacking_fixture(gw) for gw in range(6, 11)])
        saved['projection_input'].update(points_per_game=16, ep_next=0)
        saved['availability_factor'] = 0.5
        control = reweight_player(saved, 6, 'control_6gw')
        capped = reweight_player(saved, 6, 'form_12gw_minutes_cap')
        self.assertAlmostEqual(capped['projection_debug']['current_season_weight'], 63/1080)
        self.assertLess(capped['proj_5gw'], control['proj_5gw'])
        self.assertEqual(capped['projection_debug']['ep_next'], 0)
        unflagged = deepcopy(saved)
        unflagged['availability_factor'] = 1
        unflagged = reweight_player(unflagged, 6, 'form_12gw_minutes_cap')
        self.assertAlmostEqual(capped['proj_gw6'], unflagged['proj_gw6'] * 0.5)
        self.assertEqual(capped['proj_gw7'], unflagged['proj_gw7'])

    def test_chips_policy_replays_live_regression_for_every_variant(self):
        saved = saved_player(minutes=63, fixtures=[attacking_fixture(gw) for gw in range(6, 11)])
        saved['projection_input'].update(points_per_game=16, ep_next=0)
        before = deepcopy(saved)
        for variant, weight in [('control_6gw', 5/6), ('form_12gw', 5/12),
                                ('form_12gw_minutes_cap', 63/1080)]:
            with self.subTest(variant=variant):
                replay = reweight_player(saved, 6, variant, 'chips')
                expected = project_gameweeks(
                    saved['projection_input'], saved['fixtures'], 6, 10,
                    long_range_regression=True, current_season_weight_override=weight)
                for gw in range(6, 11):
                    self.assertAlmostEqual(replay[f'proj_gw{gw}'],
                                           expected[gw] * (saved['availability_factor'] if gw == 6 else 1))
                weekly = reweight_player(saved, 6, variant, 'weekly')
                self.assertNotAlmostEqual(replay['proj_gw7'], weekly['proj_gw7'])
        self.assertEqual(saved, before)

    def test_supplied_gw6_examples_preserve_captain_but_change_vice(self):
        rows = [
            ('Groß', 'MID', 9.4, 4.008829339143064, .2535, 10.7, 1.009827113858007),
            ('Bogle', 'DEF', 8.4, 2.8, .2740541666666667, 11.3, .8995064937271191),
            ('Haaland', 'FWD', 7.8, 6.8, .495, 8.0, .9444926192825605),
        ]
        scores = []
        for weight in (5/6, 5/12):
            ranking = []
            for name, position, ppg, prior, underlying, ep, multiplier in rows:
                baseline = (ppg * weight + prior * (1-weight)) * .85 + underlying * .15
                projection = (.4 * ep + .6 * baseline) * (1 + (multiplier-1) * .35)
                ranking.append((calculate_captain_score({'position': position, 'planning_gameweek': 6, 'proj_gw6': projection}), name))
            scores.append([name for _, name in sorted(ranking, reverse=True)])
        self.assertEqual(scores[0], ['Groß', 'Bogle', 'Haaland'])
        self.assertEqual(scores[1], ['Groß', 'Haaland', 'Bogle'])

    def test_paid_transfer_gate_and_free_transfer_gate_match_hq(self):
        results = [{'transfers': n, 'hit_cost': hit, 'net_score': score} for n, hit, score in
                   ((0, 0, 116.914), (1, 0, 123.928), (2, 4, 125.739), (3, 8, 125.995))]
        best, _ = select_plan(results)
        self.assertEqual(best['transfers'], 1)
        best, _ = select_plan([results[0], {'transfers': 1, 'hit_cost': 0, 'net_score': 117}])
        self.assertEqual(best['transfers'], 0)
        with self.assertRaises(ValueError):
            select_plan([])

    def bundle(self):
        return {'schema_version': 1, 'model_signature': model_signature(), 'gameweek': 6,
                'captured_at': '2026-10-04T19:00:00Z', 'players': [saved_player(1), saved_player(2)],
                'current_team': {'picks': [{'element': 1}, {'element': 2}]},
                'constraints': {'must_keep_ids': [1]}}

    def test_comparison_keeps_frozen_team_and_constraints_and_omits_raw_data(self):
        bundle = self.bundle()
        before = deepcopy(bundle)
        def solve(players, team, gw, count, **constraints):
            self.assertEqual(team, before['current_team'])
            self.assertEqual(constraints['must_keep_ids'], [1])
            if count:
                return None
            squad = deepcopy(players)
            squad[0]['captain'] = True
            squad[1]['captain'] = False
            return {'transfers': 0, 'hit_cost': 0, 'net_score': 100, 'squad': squad,
                    'incoming': [], 'outgoing': [], 'vice_captain': squad[1]}
        with patch('form_sensitivity.optimise_transfers', side_effect=solve) as solver:
            report = compare_frozen_inputs(bundle)
        self.assertEqual(solver.call_count, 12)
        self.assertTrue(report['captain_choice_stable'])
        self.assertTrue(report['transfer_choice_stable'])
        self.assertNotIn('current_team', report)
        self.assertEqual(bundle, before)

    def test_bad_signature_or_control_replay_stops_before_solver(self):
        for bad_signature in (True, False):
            bundle = self.bundle()
            if bad_signature:
                bundle['model_signature'] = 'wrong'
            else:
                bundle['players'][0]['proj_gw6'] += 1
            with patch('form_sensitivity.optimise_transfers') as solver:
                with self.assertRaises(ValueError):
                    compare_frozen_inputs(bundle)
                solver.assert_not_called()

    def test_wildcard_refuses_active_constraints_before_solving(self):
        with patch('form_sensitivity.optimise_transfers') as solver:
            with self.assertRaisesRegex(ValueError, 'KEEP/INCLUDE'):
                compare_frozen_inputs(self.bundle(), include_wildcard=True)
            solver.assert_not_called()

    def test_mislabeled_chips_capture_cannot_pass_control_replay(self):
        bundle = self.bundle()
        bundle['players'] = [saved_player(i, fixtures=[attacking_fixture(gw) for gw in range(6, 11)])
                             for i in (1, 2)]
        bundle['projection_policy'] = 'chips'
        with patch('form_sensitivity.optimise_transfers') as solve:
            with self.assertRaisesRegex(ValueError, 'Control replay'):
                compare_frozen_inputs(bundle)
            solve.assert_not_called()

    def test_each_wildcard_variant_receives_same_frozen_team_and_adjusted_pool(self):
        bundle = self.bundle()
        bundle['constraints'] = {}
        before = deepcopy(bundle)
        def solve(players, team, gw, count, **constraints):
            if count:
                return None
            squad = deepcopy(players)
            squad[0]['captain'] = True
            squad[1]['captain'] = False
            return {'transfers': 0, 'hit_cost': 0, 'net_score': 100, 'squad': squad,
                    'incoming': [], 'outgoing': [], 'vice_captain': squad[1]}
        weights = []
        def wildcard(pool, team, gw, results, selected, hold):
            self.assertEqual(team, before['current_team'])
            self.assertEqual(gw, 6)
            self.assertIs(selected, hold)
            weights.append(pool[0]['projection_debug']['current_season_weight'])
            return {'changes': 0}
        with patch('form_sensitivity.optimise_transfers', side_effect=solve), \
                patch('form_sensitivity.wildcard_comparison', side_effect=wildcard):
            report = compare_frozen_inputs(bundle, include_wildcard=True)
        self.assertEqual(weights, [5/6, 5/12, 5/12])
        self.assertTrue(all('wildcard' in v for v in report['variants']))
        self.assertEqual(bundle, before)

    def test_wildcard_uses_selling_budget_and_deducts_hit_only_once(self):
        players = [reweight_player(saved_player(i), 6, 'control_6gw') for i in (1, 2, 3)]
        for p in players:
            p.update(cost=50, position_id=3, starter=True, captain=p['id'] == 1)
        team = {'picks': [{'element': 1, 'selling_price': 47},
                          {'element': 2, 'selling_price': 48}], 'transfers': {'bank': 10}}
        hold = {'squad': players[:2], 'net_score': 90, 'hit_cost': 0, 'transfers': 0}
        paid = {'squad': players[:2], 'net_score': 100, 'hit_cost': 8, 'transfers': 3}
        def horizon(pool, squad, start, end):
            self.assertIs(pool, players)
            self.assertEqual((start, end), (6, 10))
            return {'score': 250, 'weekly': [{'gameweek': gw, 'score': 50} for gw in range(6, 11)]}
        with patch('form_sensitivity.optimise_squad', return_value=[players[0], players[2]]) as solve, \
                patch('chip_planner._fixed_squad_horizon_score', side_effect=horizon):
            result = wildcard_comparison(players, team, 6, [hold, paid], paid, hold)
        solve.assert_called_once_with(players, budget_limit=105)
        self.assertEqual(result['changes'], 1)
        self.assertEqual(result['fixed_squad_evaluation']['selected_normal']['net_five_week_projection'], 242)
        self.assertEqual(result['five_week_gain_vs_selected_normal'], 8)
        self.assertEqual(result['five_week_gain_vs_highest_scoring_normal'], 8)
        self.assertNotIn('id', result['squad'][0])


class SensitivityCommandTests(unittest.TestCase):
    def test_chips_capture_uses_same_horizon_and_regression_as_live_chips(self):
        from tools import compare_form_sensitivity as command
        from chip_planner import _chip_horizon_end, _wildcard_projection_horizon_end
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(command, 'ROOT', Path(directory)), \
                patch('fpl_api.get_bootstrap') as bootstrap, \
                patch('fpl_api.get_fixtures') as fixtures, \
                patch('fpl_api.get_planning_gameweek', return_value=6), \
                patch('fpl_api.get_my_team', return_value={'picks': []}) as team, \
                patch('optimizer.load_players', return_value=[]) as players:
            bundle = command.capture_inputs('chips')
        bootstrap.assert_called_once_with(force_refresh=True, allow_stale=False)
        fixtures.assert_called_once_with(force_refresh=True, allow_stale=False)
        players.assert_called_once_with(
            projection_end_gameweek=_wildcard_projection_horizon_end(_chip_horizon_end(6)),
            long_range_regression=True)
        team.assert_called_once_with()
        self.assertEqual(bundle['projection_policy'], 'chips')

    def test_replay_refuses_projection_policy_switch_without_capture(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from tools import compare_form_sensitivity as command
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.json'
            path.write_text(json.dumps({'projection_policy': 'weekly'}))
            error = io.StringIO()
            with patch('sys.argv', ['compare', '--input', str(path), '--projection-policy', 'chips']), \
                    patch.object(command, 'compare_frozen_inputs') as compare, \
                    patch.object(command, 'capture_inputs') as capture, \
                    contextlib.redirect_stderr(error):
                with self.assertRaises(SystemExit):
                    command.main()
            compare.assert_not_called()
            capture.assert_not_called()
            self.assertIn('policy differs', error.getvalue())

    def test_capture_only_saves_private_bundle_without_solving(self):
        import contextlib
        import io
        from pathlib import Path
        import tempfile
        from tools import compare_form_sensitivity as command
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(command, 'ROOT', Path(directory)), \
                patch.object(command, 'capture_inputs', return_value={'fixture': 'private squad'}), \
                patch.object(command, 'compare_frozen_inputs') as compare, \
                patch('sys.argv', ['compare', '--capture-only']), \
                contextlib.redirect_stderr(io.StringIO()):
            command.main()
            captures = list((Path(directory) / 'data/runtime/form_sensitivity').glob('*.json'))
            self.assertEqual(len(captures), 1)
            self.assertEqual(captures[0].stat().st_mode & 0o777, 0o600)
            compare.assert_not_called()

    def test_input_replay_does_not_capture_or_rewrite_bundle(self):
        import contextlib
        import io
        from pathlib import Path
        import tempfile
        from tools import compare_form_sensitivity as command
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text('{"schema_version":1}')
            before = path.read_bytes()
            with patch.object(command, 'capture_inputs') as capture, \
                    patch.object(command, 'compare_frozen_inputs', return_value={'research_only': True}), \
                    patch('sys.argv', ['compare', '--input', str(path)]), \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                command.main()
            capture.assert_not_called()
            self.assertEqual(path.read_bytes(), before)
