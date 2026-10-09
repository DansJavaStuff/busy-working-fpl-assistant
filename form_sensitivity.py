"""Research-only comparisons on frozen projection inputs and a fixed squad state."""

from copy import deepcopy
import hashlib
from pathlib import Path

from optimizer import (
    calculate_captain_score, calculate_objective_score, optimise_squad, project_gameweeks,
)
from transfer_optimizer import (
    MINIMUM_FREE_TRANSFER_GAIN, MINIMUM_PAID_TRANSFER_GAIN, optimise_transfers,
)

class ResearchComparisonError(ValueError):
    """A safe, actionable validation error from the research comparison."""


VARIANTS = ('control_6gw', 'form_12gw', 'form_12gw_minutes_cap')
PROJECTION_POLICIES = ('weekly', 'chips')


def model_signature():
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ('optimizer.py', 'player_context.py', 'transfer_optimizer.py',
                 'chip_planner.py', 'form_sensitivity.py'):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def reweight_player(player, gameweek, variant, projection_policy='weekly'):
    if variant not in VARIANTS:
        raise ResearchComparisonError('Unknown sensitivity variant')
    if projection_policy not in PROJECTION_POLICIES:
        raise ResearchComparisonError('Unknown projection policy')
    item = deepcopy(player)
    inputs = item['projection_input']
    games = inputs.get('current_season_games', 0)
    control_weight = min(games / 6, max(0, inputs['minutes']) / 1080, 1)
    weight = control_weight if variant == 'control_6gw' else min(games / 12, 1)
    if variant == 'form_12gw_minutes_cap':
        weight = min(weight, inputs['minutes'] / 1080)
    projections = project_gameweeks(
        inputs, item['fixtures'], gameweek, gameweek + 4,
        long_range_regression=projection_policy == 'chips',
        current_season_weight_override=weight,
    )
    for gw in range(gameweek, gameweek + 5):
        value = projections[gw]
        if gw == gameweek:
            value *= item['availability_factor']
        item[f'proj_gw{gw}'] = value if item.get('can_select', True) else 0
    item['proj_next'] = item[f'proj_gw{gameweek}']
    item['proj_5gw'] = sum(item[f'proj_gw{gw}'] for gw in range(gameweek, gameweek + 5))
    item['projection_debug'] = projections['_debug']
    return item


def select_plan(results):
    """Apply the original score gates for research, without the live sensitivity gate."""
    hold = next((r for r in results if r['transfers'] == 0), None)
    if hold is None:
        raise ResearchComparisonError('No feasible HOLD baseline; check squad and constraints')
    best = max(results, key=lambda r: r['net_score'])
    no_hit = max((r for r in results if r['hit_cost'] == 0), key=lambda r: r['net_score'])
    if best['hit_cost'] > 0 and best['net_score'] - no_hit['net_score'] < MINIMUM_PAID_TRANSFER_GAIN:
        best = no_hit
    if best['transfers'] > 0 and best['net_score'] - hold['net_score'] < MINIMUM_FREE_TRANSFER_GAIN:
        best = hold
    return best, hold


def player_summary(player, gameweek):
    return {
        'name': player['name'], 'position': player['position'],
        'projection': round(player[f'proj_gw{gameweek}'], 4),
        'captain_score': round(calculate_captain_score(player), 4),
        'form_weight': round(player['projection_debug']['current_season_weight'], 4),
    }


def squad_review(player, gameweek):
    """Public player diagnostics only; never expose captured private squad state."""
    return {
        **player_summary(player, gameweek),
        'price': player['cost'] / 10,
        'starter': player.get('starter', False),
        'captain': player.get('captain', False),
        'status': player.get('status'),
        'availability_percent': player.get('chance_of_playing_next_round'),
        'minutes': player['projection_input']['minutes'],
        'ppg': player['projection_debug']['ppg'],
        'ep_next': player['projection_debug']['ep_next'],
        'expected_start_probability': player['projection_debug']['expected_start_probability'],
        'weekly_projections': {
            str(gw): round(player[f'proj_gw{gw}'], 4)
            for gw in range(gameweek, gameweek + 5)
        },
        'fixtures': [{
            'gameweek': f['gw'], 'opponent': f.get('opponent_name'),
            'home': f.get('home'), 'difficulty': f.get('difficulty'),
        } for f in player['fixtures'] if gameweek <= f['gw'] < gameweek + 5],
    }


def wildcard_comparison(players, team, gameweek, results, selected, hold):
    """Compare existing selection objective and fixed-squad five-week evaluation."""
    from chip_planner import _fixed_squad_horizon_score

    budget = sum(pick['selling_price'] for pick in team['picks']) + team['transfers']['bank']
    squad = optimise_squad(players, budget_limit=budget)
    score = calculate_objective_score(squad)
    highest = max(results, key=lambda r: r['net_score'])
    no_hit = max((r for r in results if r['hit_cost'] == 0), key=lambda r: r['net_score'])
    owned = {pick['element'] for pick in team['picks']}
    evaluations = {}
    for label, plan_squad, hit in (
        ('hold', hold['squad'], hold['hit_cost']),
        ('best_no_hit', no_hit['squad'], no_hit['hit_cost']),
        ('selected_normal', selected['squad'], selected['hit_cost']),
        ('highest_scoring_normal', highest['squad'], highest['hit_cost']),
        ('wildcard', squad, 0),
    ):
        horizon = _fixed_squad_horizon_score(players, plan_squad, gameweek, gameweek + 4)
        if horizon is None:
            raise ResearchComparisonError('Cannot evaluate a complete legal fixed squad')
        evaluations[label] = {
            'weekly': [{**row, 'score': round(row['score'], 4)} for row in horizon['weekly']],
            'hit_cost_once': hit,
            'net_five_week_projection': round(horizon['score'] - hit, 4),
        }
    wc_net = evaluations['wildcard']['net_five_week_projection']
    return {
        'budget': budget / 10, 'squad_cost': sum(p['cost'] for p in squad) / 10,
        'changes': sum(p['id'] not in owned for p in squad),
        'model_gain_vs_hold': round(score - hold['net_score'], 4),
        'model_gain_vs_selected_normal': round(score - selected['net_score'], 4),
        'model_gain_vs_highest_scoring_normal': round(score - highest['net_score'], 4),
        'highest_scoring_normal_transfers': highest['transfers'],
        'highest_scoring_normal_hit': highest['hit_cost'],
        'fixed_squad_evaluation': evaluations,
        'five_week_gain_vs_selected_normal': round(
            wc_net - evaluations['selected_normal']['net_five_week_projection'], 4),
        'five_week_gain_vs_highest_scoring_normal': round(
            wc_net - evaluations['highest_scoring_normal']['net_five_week_projection'], 4),
        'squad': [squad_review(p, gameweek) for p in sorted(
            squad, key=lambda p: (p['position_id'], p['name']))],
    }


def compare_frozen_inputs(bundle, progress=None, include_wildcard=False):
    if bundle.get('schema_version') != 1 or bundle.get('model_signature') != model_signature():
        raise ResearchComparisonError('Input schema/model differs; capture a new bundle with this code version')
    gameweek = bundle['gameweek']
    projection_policy = bundle.get('projection_policy', 'weekly')
    if projection_policy not in PROJECTION_POLICIES:
        raise ResearchComparisonError('Unknown projection policy')
    players = bundle['players']
    if any(p.get('planning_gameweek') != gameweek for p in players):
        raise ResearchComparisonError('Captured players do not match the planning Gameweek')
    constraints = bundle.get('constraints', {})
    if include_wildcard and any(constraints.get(key) for key in ('must_keep_ids', 'must_include_ids')):
        raise ResearchComparisonError('Wildcard comparison requires no active KEEP/INCLUDE constraints')
    control = [reweight_player(p, gameweek, 'control_6gw', projection_policy) for p in players]
    # Refuse to compare if the replay cannot reproduce the captured live projections.
    for saved, replayed in zip(players, control):
        for gw in range(gameweek, gameweek + 5):
            if abs(saved[f'proj_gw{gw}'] - replayed[f'proj_gw{gw}']) > 1e-9:
                raise ResearchComparisonError('Control replay does not match captured projections')
    owned = {pick['element'] for pick in bundle['current_team']['picks']}
    variants = []
    transfer_choices, captain_choices, vice_choices = set(), set(), set()
    for variant in VARIANTS:
        if progress:
            progress(variant)
        adjusted = control if variant == 'control_6gw' else [
            reweight_player(p, gameweek, variant, projection_policy) for p in players]
        results = []
        for count in range(4):
            result = optimise_transfers(
                adjusted, bundle['current_team'], gameweek, count,
                must_keep_ids=constraints.get('must_keep_ids', []),
                must_include_ids=constraints.get('must_include_ids', []),
            )
            if result is not None:
                results.append(result)
        best, hold = select_plan(results)
        captain = next(p for p in best['squad'] if p['captain'])
        pairs = []
        incoming = list(best['incoming'])
        for outgoing in best['outgoing']:
            match = next(p for p in incoming if p['position'] == outgoing['position'])
            pairs.append({'out': outgoing['name'], 'in': match['name']})
            incoming.remove(match)
        transfer_choices.add((best['transfers'], best['hit_cost'],
                              tuple(sorted(p['id'] for p in best['outgoing'])),
                              tuple(sorted(p['id'] for p in best['incoming']))))
        captain_choices.add(captain['id'])
        vice_choices.add(best['vice_captain']['id'])
        summary = {
            'variant': variant, 'transfers': best['transfers'], 'hit_cost': best['hit_cost'],
            'net_model_gain': round(best['net_score'] - hold['net_score'], 4),
            'pairs': pairs, 'captain': player_summary(captain, gameweek),
            'vice': player_summary(best['vice_captain'], gameweek),
            'owned_captain_ranking': [player_summary(p, gameweek) for p in sorted(
                (p for p in adjusted if p['id'] in owned),
                key=calculate_captain_score, reverse=True)[:5]],
            'scenarios': [{
                'transfers': r['transfers'], 'hit_cost': r['hit_cost'],
                'net_gain': round(r['net_score'] - hold['net_score'], 4),
            } for r in results],
        }
        if include_wildcard:
            if progress:
                progress(variant + ': wildcard and fixed-squad five-week evaluation')
            summary['wildcard'] = wildcard_comparison(
                adjusted, bundle['current_team'], gameweek, results, best, hold)
            summary['watch_players'] = [squad_review(p, gameweek) for p in adjusted
                                       if p['name'] in ('Hinshelwood', 'Semenyo')]
        variants.append(summary)
    return {
        'research_only': True, 'gameweek': gameweek, 'captured_at': bundle['captured_at'],
        'projection_policy': projection_policy,
        'long_range_regression': projection_policy == 'chips',
        'live_paid_sensitivity_gate_applied': False,
        'variants': variants,
        'transfer_choice_stable': len(transfer_choices) == 1,
        'captain_choice_stable': len(captain_choices) == 1,
        'vice_choice_stable': len(vice_choices) == 1,
        'note': 'Sensitivity is not calibration or proof of accuracy. This tool does not change live weights. '
                'Research plans use the original score gates; the additional live paid-plan '
                'sensitivity gate is not applied, so plan choices may differ from HQ. '
                'Official ep_next, fixtures, availability, priors, captain weights and transfer gates '
                'are fixed across variants. No future injury/news forecast is made. '
                + ('All variants retain the live Chips long-range regression unchanged. '
                   if projection_policy == 'chips' else 'All variants use weekly planner projection defaults. ')
                + ('Wildcard uses the existing GW XI/captain plus 15% squad five-week objective. '
                   'Five-week evaluations hold each selected squad fixed, reselect XI/captain weekly '
                   'and deduct the initial hit once; no later transfers, autosubs, price changes or '
                   'chip timing decision are simulated. Availability penalties remain GW-only. '
                   'This does not update the live Chips page.'
                   if include_wildcard else 'No chip comparison is made.'),
    }
