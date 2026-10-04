from copy import deepcopy
import unittest
from unittest.mock import patch

from form_sensitivity import compare_frozen_inputs, model_signature, reweight_player, select_plan
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


class SensitivityCommandTests(unittest.TestCase):
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
