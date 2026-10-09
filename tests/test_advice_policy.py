from copy import deepcopy
import unittest
from unittest.mock import patch

from advice_policy import cautious_paid_plan_check, lineup_summary
from optimizer import calculate_objective_score, project_gameweeks
from chip_planner import _current_squad_lineup
from tests.test_special_gameweeks import projection_player, attacking_fixture


def pool():
    result = []
    for i, position in enumerate(['GKP']*2 + ['DEF']*5 + ['MID']*5 + ['FWD']*3, 1):
        inputs = projection_player()
        inputs.update(position=position, current_season_games=5, minutes=450,
                      points_per_game=5, ep_next=0)
        fixtures = [attacking_fixture(gw) for gw in range(6, 11)]
        projections = project_gameweeks(inputs, fixtures, 6, 10)
        p = {'id': i, 'name': str(i), 'position': position, 'position_id':
             {'GKP':1,'DEF':2,'MID':3,'FWD':4}[position],
             'planning_gameweek':6, 'projection_input':inputs, 'fixtures':fixtures,
             'availability_factor':1, 'can_select':True}
        p.update({f'proj_gw{gw}': projections[gw] for gw in range(6,11)})
        p['proj_next'] = p['proj_gw6']
        p['proj_5gw'] = sum(p[f'proj_gw{gw}'] for gw in range(6,11))
        result.append(p)
    return result


class AdvicePolicyTests(unittest.TestCase):
    def test_production_weight_caps_63_minutes_without_changing_ep(self):
        inputs = projection_player()
        inputs.update(current_season_games=5, minutes=63, points_per_game=16, ep_next=0)
        projections = project_gameweeks(inputs, [attacking_fixture(6)], 6)
        self.assertAlmostEqual(projections['_debug']['current_season_weight'], 63/1080)
        self.assertEqual(projections['_debug']['ep_next'], 0)
        legacy = project_gameweeks(inputs, [attacking_fixture(6)], 6, current_season_weight_override=5/6)
        self.assertLess(projections[6], legacy[6])
        inputs['minutes'] = 1800
        self.assertAlmostEqual(project_gameweeks(inputs, [], 6)['_debug']['current_season_weight'], 5/6)

    def test_paid_check_reoptimises_lineups_and_subtracts_12_point_hit_once(self):
        players = pool()
        before = deepcopy(players)
        plan = {'squad':players, 'hit_cost':0, 'transfers':0}
        paid = {**plan, 'hit_cost':12, 'transfers':3}
        result = cautious_paid_plan_check(players, paid, plan, 6)
        self.assertEqual(result['cautious_net_gain'], -12)
        self.assertFalse(result['passed'])
        self.assertEqual(players, before)

    def test_boundary_and_stronger_plan_can_pass_without_api_or_solver(self):
        players = pool()
        replacement = deepcopy(players[-1])
        replacement.update(id=16, proj_gw6=100, proj_next=100, proj_5gw=100)
        paid = {'squad': players[:-1]+[replacement], 'hit_cost':4, 'transfers':1}
        hold = {'squad':players, 'hit_cost':0, 'transfers':0}
        with patch('advice_policy.reweight_player', side_effect=lambda p,*args:p):
            result = cautious_paid_plan_check(players+[replacement], paid, hold, 6)
        self.assertTrue(result['passed'])
        self.assertEqual(result['required_gain'], 3)

    def test_gate_boundary_includes_hit_and_uses_net_gain(self):
        players = pool()
        hold = {'squad':players, 'hit_cost':0, 'transfers':0}
        paid = {'squad':players, 'hit_cost':12, 'transfers':3}
        for gross, passed in ((14.99, False), (15, True)):
            with self.subTest(gross=gross), patch(
                'advice_policy.calculate_objective_score', side_effect=[100+gross,100]
            ):
                result = cautious_paid_plan_check(players, paid, hold, 6)
                self.assertAlmostEqual(result['cautious_net_gain'],gross-12)
                self.assertEqual(result['passed'],passed)

    def test_hold_lineup_is_legal_owned_only_with_captain_and_bench_order(self):
        players = pool()
        team = {'picks':[{'element':p['id']} for p in players]}
        result = _current_squad_lineup(players, team, 6)
        view = lineup_summary(result, 6)
        self.assertEqual(len(view['starters']),11)
        self.assertEqual(len(view['bench']),4)
        self.assertEqual(view['bench'][0]['position'],'GKP')
        self.assertNotEqual(view['captain']['id'],view['vice']['id'])
        self.assertEqual({p['id'] for p in view['starters']+view['bench']},set(range(1,16)))
        self.assertGreater(calculate_objective_score(result['squad']),0)
