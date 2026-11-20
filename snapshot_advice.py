"""Copy existing advice into a snapshot without computing or fetching anything."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path

REPORT_PATH = Path(__file__).resolve().parent / 'data/weekly_report.json'


def frozen_advice(gameweek, captured_at, current_team, report_path=REPORT_PATH):
    try:
        report = json.loads(Path(report_path).read_text(encoding='utf-8'))
        generated = datetime.fromisoformat(report['generated_at'].replace('Z','+00:00'))
        captured = datetime.fromisoformat(captured_at.replace('Z','+00:00'))
        if generated.tzinfo is None or captured.tzinfo is None or generated > captured:
            return {'status':'invalid_report_time'}
        if report['gameweek'] != gameweek:
            return {'status':'different_gameweek'}
        current = report['current_starters'] + report['current_bench']
        owned = {p['element'] for p in current_team['picks']}
        if len(owned) != 15 or {p['id'] for p in current} != owned:
            return {'status':'different_owned_squad'}
        recommended = report['recommended']['squad']
        values = {}
        for p in current + recommended:
            value = float(p[f'proj_gw{gameweek}'])
            if not math.isfinite(value) or (p['id'] in values and values[p['id']] != value):
                return {'status':'invalid_projection'}
            values[p['id']] = value
        players = {p['id']:p for p in current + recommended}
        projections = []
        for p in players.values():
            value = float(p[f'proj_gw{gameweek}'])
            if not math.isfinite(value):
                return {'status':'invalid_projection'}
            projections.append({'id':p['id'], 'name':p['name'], 'projection':value,
                                'was_owned':p['id'] in owned})
        return {'status':'saved', 'gameweek':gameweek,
                'generated_at':generated.astimezone(timezone.utc).isoformat(),
                'age_at_capture_seconds':(captured-generated).total_seconds(),
                'schema_version':report.get('schema_version'),
                'model_version':report.get('model_version'),
                'players':projections, 'captain_id':report['captain']['id'],
                'vice_id':report['vice']['id'],
                'hold_captain_id':(report.get('hold_lineup') or {}).get('captain',{}).get('id'),
                'recommended_transfers':report['recommended']['transfers'],
                'hit_cost':report['recommended']['hit_cost']}
    except FileNotFoundError:
        return {'status':'no_saved_report'}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return {'status':'invalid_saved_report'}
