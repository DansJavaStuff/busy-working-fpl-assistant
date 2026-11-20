"""Audit frozen pre-deadline inputs and evaluate captured FPL estimates.

This module never imports the application, opens credentials, migrates the DB,
reconstructs app projections, or submits FPL changes.
"""
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from urllib.request import urlopen

CHECKPOINTS = {'baseline': 3600, 't60m': 3600, 't15m': 900, 't10m': 600, 't5m': 300}
TOLERANCE_SECONDS = 180
DEFAULT_DB_PATH = Path(__file__).resolve().parent / 'data/runtime/fpl_history.db'


def utc_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return result.astimezone(timezone.utc)


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def season_key(bootstrap):
    event = next(e for e in bootstrap['events'] if e.get('id') == 1)
    year = utc_time(event['deadline_time']).year
    return f'{year}-{str(year + 1)[-2:]}'


def assess_snapshot(row, now):
    """Use captured timestamps and deadline, never the payload's timing claims."""
    checkpoint = row['snapshot_type'].removeprefix('pre_deadline_')
    result = {'snapshot_id': row['id'], 'checkpoint': checkpoint,
              'captured_at': row['captured_at'], 'issues': [],
              'timing': 'unknown', 'data_complete': False,
              'ep_next_aligned': False, 'eligible': False}
    payload = None
    try:
        payload = json.loads(row['payload_json'])
        if not isinstance(payload, dict):
            raise ValueError('Payload must be an object')
        bootstrap = payload.get('bootstrap') or {}
        if not isinstance(bootstrap, dict):
            raise ValueError('Bootstrap must be an object')
        events = bootstrap.get('events') or []
        elements = bootstrap.get('elements') or []
        team = payload.get('current_team') or {}
        picks = team.get('picks') or []
        event = next((e for e in events if e.get('id') == row['gameweek']), None)
        captured = utc_time(row['captured_at'])
        deadline_text = payload.get('deadline') or (event or {}).get('deadline_time')
        deadline = utc_time(deadline_text)
        remaining = (deadline - captured).total_seconds()
        result.update(deadline_time=deadline_text, seconds_remaining=remaining)
        if captured > now:
            result['issues'].append('capture_in_future')
        if checkpoint not in CHECKPOINTS:
            result['issues'].append('unknown_checkpoint')
        else:
            target = CHECKPOINTS[checkpoint]
            result['timing'] = 'after_deadline' if remaining <= 0 else (
                'on_time' if (remaining > target if checkpoint == 'baseline'
                              else target - TOLERANCE_SECONDS <= remaining <= target)
                else 'outside_window')
        if not event or utc_time(event['deadline_time']) != deadline:
            result['issues'].append('captured_deadline_mismatch')
        if payload.get('captured_at') and utc_time(payload['captured_at']) != captured:
            result['issues'].append('capture_timestamp_mismatch')
        if season_key(bootstrap) != row['season_key']:
            result['issues'].append('captured_season_mismatch')
        ids = [p['id'] for p in elements]
        pick_ids = [p['element'] for p in picks]
        positions = [p['position'] for p in picks]
        complete = (
            bool(elements) and len(ids) == len(set(ids))
            and bool(bootstrap.get('teams'))
            and isinstance(payload.get('fixtures'), list) and bool(payload['fixtures'])
            and len(picks) == 15 and len(set(pick_ids)) == 15
            and set(pick_ids).issubset(ids) and sorted(positions) == list(range(1,16))
            and sum(bool(p.get('is_captain')) for p in picks) == 1
            and sum(bool(p.get('is_vice_captain')) for p in picks) == 1
            and not any(p.get('is_captain') and p.get('is_vice_captain') for p in picks)
            and all(p['position'] <= 11 for p in picks
                    if p.get('is_captain') or p.get('is_vice_captain'))
        )
        result['data_complete'] = complete
        if not complete:
            result['issues'].append('missing_or_invalid_required_data')
        result['ep_next_aligned'] = (
            len([e for e in events if e.get('is_next')]) == 1
            and any(e.get('is_next') and e.get('id') == row['gameweek'] for e in events)
        )
        if not result['ep_next_aligned']:
            result['issues'].append('ep_next_event_not_verified')
        result['eligible'] = (
            not result['issues'] and remaining > 0 and complete
        )
        advice = payload.get('app_advice')
        result['app_advice_status'] = (advice.get('status', 'invalid_saved_advice')
                                      if isinstance(advice, dict) else 'not_recorded' if advice is None else 'invalid_saved_advice')
    except (ValueError, TypeError, KeyError, AttributeError, StopIteration):
        result['issues'].append('malformed_payload_or_timestamp')
        result['eligible'] = False
    return result, payload


def _metrics(pairs):
    if not pairs:
        return None
    errors = [predicted - actual for predicted, actual in pairs]
    return {'n': len(pairs), 'mae': sum(abs(e) for e in errors) / len(errors),
            'bias': sum(errors) / len(errors),
            'rmse': math.sqrt(sum(e*e for e in errors) / len(errors))}


def evaluate_payload(payload, live):
    """Compare two captured signals on identical IDs; absent outcomes stay missing."""
    stats = {}
    for p in live['elements']:
        if p['id'] in stats:
            raise ValueError('Duplicate outcome player ID')
        stats[p['id']] = p['stats']
    players = {p['id']: p for p in payload['bootstrap']['elements']}
    picks = payload['current_team']['picks']
    owned = {p['element'] for p in picks}
    cohorts = {}
    for name, ids in (
        ('all_players', set(players)),
        ('previously_played', {i for i,p in players.items() if (number(p.get('minutes')) or 0) > 0}),
        ('owned_players', owned),
    ):
        pairs = []
        for i in sorted(ids):
            p = players[i]
            ep, ppg = number(p.get('ep_next')), number(p.get('points_per_game'))
            actual = number(stats.get(i, {}).get('total_points'))
            if ep is not None and ppg is not None and actual is not None:
                pairs.append((ep, ppg, actual))
        cohorts[name] = {'candidate_players': len(ids), 'matched_players': len(pairs),
                         'unmatched_players': len(ids)-len(pairs),
                         'captured_ep_next': _metrics([(ep,a) for ep,_,a in pairs]),
                         'captured_ppg_baseline': _metrics([(ppg,a) for _,ppg,a in pairs])}
    starters = [players[p['element']] for p in picks if p['position'] <= 11]
    recorded = next(players[p['element']] for p in picks if p.get('is_captain'))

    def captain_record(p):
        result = stats.get(p['id'], {})
        return {'name': p.get('web_name'), 'player_id': p['id'],
                'captured_ep_next': number(p.get('ep_next')),
                'captured_ppg': number(p.get('points_per_game')),
                'actual_player_points': number(result.get('total_points')),
                'actual_minutes': number(result.get('minutes'))}

    captains = {'recorded_snapshot_captain': captain_record(recorded)}
    for field, label in [('ep_next','highest_captured_ep_next_in_snapshot_xi'),
                         ('points_per_game','highest_captured_ppg_in_snapshot_xi')]:
        candidates = [p for p in starters if number(p.get(field)) is not None]
        # Complete forecast coverage is required to claim a highest-ranked player.
        captains[label] = captain_record(max(
            candidates, key=lambda p: (number(p[field]), -p['id'])
        )) if len(candidates) == len(starters) else None
    haaland = next((p for p in starters if p.get('web_name') == 'Haaland'), None)
    captains['haaland_if_in_snapshot_xi'] = captain_record(haaland) if haaland else None
    advice = payload.get('app_advice') or {}
    if not isinstance(advice, dict):
        advice = {'status':'invalid_saved_advice'}
    app_evaluation = {'status': advice.get('status', 'not_recorded')}
    if advice.get('status') == 'saved':
        try:
            generated = utc_time(advice['generated_at'])
            captured = utc_time(payload['captured_at'])
            if generated > captured or advice['gameweek'] != next(
                e['id'] for e in payload['bootstrap']['events'] if e.get('is_next')
            ):
                raise ValueError('Advice time/event mismatch')
            predictions = advice['players']
            if len({p['id'] for p in predictions}) != len(predictions):
                raise ValueError('Duplicate advice player')
            pairs = []
            for p in predictions:
                if p['id'] in owned:
                    forecast = number(p.get('projection'))
                    actual = number(stats.get(p['id'], {}).get('total_points'))
                    if forecast is not None and actual is not None:
                        pairs.append((forecast,actual))
            def advice_captain(key):
                i = advice.get(key)
                p = next((p for p in predictions if p['id'] == i), None)
                return {'player_id':i, 'name':p.get('name'),
                        'projection':number(p.get('projection')),
                        'actual_player_points':number(stats.get(i,{}).get('total_points')),
                        'actual_minutes':number(stats.get(i,{}).get('minutes'))} if p else None
            app_evaluation = {
                'status':'evaluated_saved_advice', 'generated_at':advice['generated_at'],
                'age_at_capture_seconds':(captured-generated).total_seconds(),
                'model_version':advice.get('model_version'),
                'owned_players_matched':len(pairs), 'owned_projection_error':_metrics(pairs),
                'recommended_captain':advice_captain('captain_id'),
                'hold_captain':advice_captain('hold_captain_id'),
                'recommended_transfers':advice.get('recommended_transfers'),
                'hit_cost':advice.get('hit_cost'),
            }
        except (ValueError, TypeError, KeyError, AttributeError, StopIteration):
            app_evaluation = {'status':'invalid_saved_advice'}
    return {'cohorts': cohorts, 'captain_player_comparison': captains,
            'saved_app_advice':app_evaluation}


class OfficialOutcomes:
    """Public read requests only; retain one response per GW in memory."""
    def __init__(self, fetch=None):
        self.fetch = fetch or self._fetch
        self.bootstrap = self.fetch('bootstrap-static/')
        self.season = season_key(self.bootstrap)
        self.events = {e['id']: e for e in self.bootstrap['events']}
        self.cache = {}

    @staticmethod
    def _fetch(path):
        with urlopen('https://fantasy.premierleague.com/api/' + path, timeout=30) as response:
            return json.load(response)

    def __call__(self, season, gameweek):
        if season != self.season:
            return {'status': 'different_season'}
        event = self.events.get(gameweek, {})
        if not (event.get('finished') is True and event.get('data_checked') is True):
            return {'status': 'pending_or_unchecked_results'}
        if gameweek not in self.cache:
            try:
                live = self.fetch(f'event/{gameweek}/live/')
                if not isinstance(live.get('elements'), list) or not live['elements']:
                    raise ValueError('Missing live elements')
                self.cache[gameweek] = {
                    'status': 'ready', 'live': live,
                    'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'source': f'https://fantasy.premierleague.com/api/event/{gameweek}/live/',
                }
            except (OSError, ValueError, TypeError, AttributeError):
                self.cache[gameweek] = {'status': 'outcome_fetch_failed'}
        return self.cache[gameweek]


def snapshot_report(db_path=DEFAULT_DB_PATH, now=None, outcome_loader=None,
                    season=None, checkpoint='latest'):
    now = now or datetime.now(timezone.utc)
    if checkpoint not in {'latest', *CHECKPOINTS}:
        raise ValueError('Unknown checkpoint selection')
    connection = sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only = ON')
        connection.execute('BEGIN')
        rows = connection.execute('''
            SELECT p.id, p.entry_id, p.snapshot_type, p.captured_at, p.payload_json,
                   s.season_key, g.gameweek, g.deadline_time
            FROM snapshots p JOIN gameweeks g ON g.id = p.gameweek_id
            JOIN seasons s ON s.id = p.season_id
            WHERE p.source = 'official_fpl_live'
              AND p.snapshot_type LIKE 'pre_deadline_%'
              AND g.season_id = p.season_id
            ORDER BY s.season_key, p.entry_id, g.gameweek, p.captured_at, p.id
        ''').fetchall()
    finally:
        connection.close()
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if season is None or row['season_key'] == season:
            groups[(row['season_key'], row['entry_id'])][row['gameweek']].append(row)
    weeks = []
    for entry_number, ((season_name, _), gameweeks) in enumerate(groups.items(), 1):
        for gw in range(min(gameweeks), max(gameweeks)+1):
            assessments = [assess_snapshot(row, now) for row in gameweeks.get(gw, [])]
            coverage = []
            eligible = []
            for assessment, payload in assessments:
                coverage.append(assessment)
                if assessment['eligible'] and (checkpoint == 'latest' or assessment['checkpoint'] == checkpoint):
                    eligible.append((assessment, payload))
            # One record per entry/GW. Five checkpoints are not five independent weeks.
            selected = max(eligible, key=lambda pair: (utc_time(pair[0]['captured_at']), pair[0]['snapshot_id'])) if eligible else None
            deadline_text = next((a.get('deadline_time') for a in coverage if a.get('deadline_time')), None)
            remaining = (utc_time(deadline_text)-now).total_seconds() if deadline_text else None
            checkpoint_status = {}
            for label, target in CHECKPOINTS.items():
                present = [a for a in coverage if a['checkpoint'] == label]
                checkpoint_status[label] = (
                    'saved_eligible' if any(a['eligible'] for a in present)
                    else 'saved_invalid' if present
                    else 'pending' if remaining is not None and remaining > target
                    else 'missing'
                )
            week = {'season_key': season_name, 'entry_group': entry_number, 'gameweek': gw,
                    'stored_snapshots': len(assessments), 'checkpoint_status':checkpoint_status,
                    'missing_checkpoints': [label for label in CHECKPOINTS if not any(
                        a['checkpoint'] == label for a in coverage)],
                    'valid_checkpoints': sorted({a['checkpoint'] for a in coverage if a['eligible']}),
                    'snapshots': coverage,
                    'selected_snapshot_id': selected[0]['snapshot_id'] if selected else None,
                    'outcome_status': 'no_eligible_snapshot' if not selected else 'not_requested'}
            if selected and outcome_loader:
                outcome = outcome_loader(season_name, gw)
                week['outcome_status'] = outcome['status']
                if outcome['status'] == 'ready':
                    try:
                        week['evaluation'] = evaluate_payload(selected[1], outcome['live'])
                        week['outcome_status'] = 'evaluated'
                        week['outcome_source'] = outcome.get('source')
                        week['outcome_retrieved_at'] = outcome.get('retrieved_at')
                    except (ValueError, TypeError, KeyError, AttributeError):
                        week['outcome_status'] = 'invalid_outcome_data'
            weeks.append(week)
    evaluated = {(w['season_key'],w['gameweek']) for w in weeks if w['outcome_status'] == 'evaluated'}
    return {'schema_version': 1, 'generated_at': now.isoformat(),
            'selection_policy': checkpoint,
            'summary': {'entry_gameweeks': len(weeks),
                        'gameweeks_with_eligible_snapshots': len({(w['season_key'],w['gameweek']) for w in weeks if w['selected_snapshot_id'] is not None}),
                        'distinct_gameweeks_evaluated': len(evaluated)},
            'weeks': weeks,
            'notes': [
                'Older snapshots contain raw inputs only. App advice is evaluated only when explicitly saved in the snapshot; older app predictions are never reconstructed.',
                'Saved app advice may predate raw inputs: inspect its age. App error and captured ep_next error are not a controlled same-input model comparison. Unknown model versions remain null.',
                'Evaluation uses captured ep_next and a captured PPG baseline on identical matched players. Missing/nonfinite values are excluded, not zero-filled.',
                'One selected pre-deadline snapshot per entry/Gameweek; repeated players and entries are not independent experimental samples.',
                'Latest means latest eligible capture. An otherwise valid capture outside its checkpoint window can be selected; inspect timing and missing checkpoints.',
                'Captain comparisons are individual player points within the captured XI: no doubling, vice fallback, auto-subs, chips or transfer hits. Snapshot picks may differ from final submitted picks.',
                'Current results may include later scoring corrections. Weeks without finished and data_checked flags remain pending. No statistical confidence or accuracy-improvement claim.',
                'Database is read-only; no migrations, credentials, app cache writes or FPL submissions. Entry IDs and raw payloads are omitted.',
            ]}
