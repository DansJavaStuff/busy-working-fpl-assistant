"""Research-only comparisons on frozen projection inputs and a fixed squad state."""

from copy import deepcopy
import hashlib
from pathlib import Path

from optimizer import calculate_captain_score, project_gameweeks
from transfer_optimizer import (
    MINIMUM_FREE_TRANSFER_GAIN, MINIMUM_PAID_TRANSFER_GAIN, optimise_transfers,
)

VARIANTS = ('control_6gw', 'form_12gw', 'form_12gw_minutes_cap')


def model_signature():
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ('optimizer.py', 'player_context.py', 'transfer_optimizer.py', 'form_sensitivity.py'):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def reweight_player(player, gameweek, variant):
    if variant not in VARIANTS:
        raise ValueError('Unknown sensitivity variant')
    item = deepcopy(player)
    inputs = item['projection_input']
    games = inputs.get('current_season_games', 0)
    control_weight = min(games / 6, 1)
    weight = control_weight if variant == 'control_6gw' else min(games / 12, 1)
    if variant == 'form_12gw_minutes_cap':
        weight = min(weight, inputs['minutes'] / 1080)
    projections = project_gameweeks(
        inputs, item['fixtures'], gameweek, gameweek + 4,
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
    """Reproduce HQ's existing net-score gates, without submitting changes."""
    hold = next((r for r in results if r['transfers'] == 0), None)
    if hold is None:
        raise ValueError('No feasible HOLD baseline; check squad and constraints')
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


def compare_frozen_inputs(bundle, progress=None):
    if bundle.get('schema_version') != 1 or bundle.get('model_signature') != model_signature():
        raise ValueError('Input schema/model differs; capture a new bundle with this code version')
    gameweek = bundle['gameweek']
    players = bundle['players']
    if any(p.get('planning_gameweek') != gameweek for p in players):
        raise ValueError('Captured players do not match the planning Gameweek')
    control = [reweight_player(p, gameweek, 'control_6gw') for p in players]
    # Refuse to compare if the replay cannot reproduce the captured live projections.
    for saved, replayed in zip(players, control):
        for gw in range(gameweek, gameweek + 5):
            if abs(saved[f'proj_gw{gw}'] - replayed[f'proj_gw{gw}']) > 1e-9:
                raise ValueError('Control replay does not match captured projections')
    owned = {pick['element'] for pick in bundle['current_team']['picks']}
    variants = []
    transfer_choices, captain_choices, vice_choices = set(), set(), set()
    constraints = bundle.get('constraints', {})
    for variant in VARIANTS:
        if progress:
            progress(variant)
        adjusted = control if variant == 'control_6gw' else [
            reweight_player(p, gameweek, variant) for p in players]
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
        variants.append({
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
        })
    return {
        'research_only': True, 'gameweek': gameweek, 'captured_at': bundle['captured_at'],
        'variants': variants,
        'transfer_choice_stable': len(transfer_choices) == 1,
        'captain_choice_stable': len(captain_choices) == 1,
        'vice_choice_stable': len(vice_choices) == 1,
        'note': 'Sensitivity is not calibration or proof of accuracy. Live weights remain unchanged. '
                'Official ep_next, fixtures, availability, priors, captain weights and transfer gates '
                'are fixed across variants. No chip comparison or future injury/news forecast is made.',
    }
