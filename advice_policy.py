"""Checks on frozen inputs before recommending additional paid transfers."""
from chip_planner import _current_squad_lineup
from form_sensitivity import reweight_player
from optimizer import calculate_captain_score, calculate_objective_score
from transfer_optimizer import MINIMUM_PAID_TRANSFER_GAIN


def lineup_summary(result, gameweek):
    squad = result['squad']
    starters = sorted((p for p in squad if p['starter']),
                      key=lambda p: (p['position_id'], -p[f'proj_gw{gameweek}']))
    bench = sorted((p for p in squad if not p['starter']),
                   key=lambda p: (p['position'] != 'GKP', -p[f'proj_gw{gameweek}']))
    captain = next(p for p in starters if p['captain'])
    vice = max((p for p in starters if p['id'] != captain['id']),
               key=calculate_captain_score)
    return {'starters': starters, 'bench': bench, 'captain': captain, 'vice': vice}


def cautious_paid_plan_check(players, paid, no_hit, gameweek):
    """Reoptimise XI only for the same two squads; subtract each hit once.

    This checks sensitivity of the proposed purchases, not their accuracy or
    the best alternative purchases under the cautious projection. No CBC/API.
    """
    cautious = [reweight_player(p, gameweek, 'form_12gw_minutes_cap') for p in players]
    scores = []
    for plan in (paid, no_hit):
        team = {'picks': [{'element': p['id']} for p in plan['squad']]}
        lineup = _current_squad_lineup(cautious, team, gameweek)
        if lineup is None:
            raise ValueError('Cannot check paid transfers without a complete legal squad')
        scores.append(calculate_objective_score(lineup['squad']) - plan['hit_cost'])
    gain = scores[0] - scores[1]
    return {'passed': gain >= MINIMUM_PAID_TRANSFER_GAIN,
            'cautious_net_gain': gain, 'required_gain': MINIMUM_PAID_TRANSFER_GAIN,
            'transfers': paid['transfers'], 'hit_cost': paid['hit_cost'],
            'baseline_transfers': no_hit['transfers']}
