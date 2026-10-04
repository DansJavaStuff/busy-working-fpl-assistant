"""Compare early-form weights on one frozen input bundle; never apply FPL changes."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

from form_sensitivity import compare_frozen_inputs, model_signature

ROOT = Path(__file__).resolve().parents[1]


def capture_inputs():
    # Imported only for explicit capture; --input replays without these API calls.
    from fpl_api import get_bootstrap, get_fixtures, get_my_team, get_planning_gameweek
    from optimizer import load_players

    get_bootstrap(force_refresh=True, allow_stale=False)
    get_fixtures(force_refresh=True, allow_stale=False)
    gameweek = get_planning_gameweek()
    players = load_players()
    team = get_my_team()
    constraints = {}
    path = ROOT / 'data/weekly_report.json'
    if path.exists():
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('gameweek') == gameweek:
            constraints = report.get('constraints', {})
    return {
        'schema_version': 1, 'model_signature': model_signature(),
        'gameweek': gameweek, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'players': players, 'current_team': team, 'constraints': constraints,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Replay an existing frozen JSON bundle offline')
    parser.add_argument('--capture-only', action='store_true', help='Save inputs without solving')
    args = parser.parse_args()
    if args.input and args.capture_only:
        parser.error('--capture-only cannot be combined with --input')
    try:
        if args.input:
            bundle = json.loads(args.input.read_text(encoding='utf-8'))
            input_path = args.input
        else:
            print('Capturing official inputs and squad; no FPL changes will be submitted.', file=sys.stderr)
            bundle = capture_inputs()
            directory = ROOT / 'data/runtime/form_sensitivity'
            directory.mkdir(parents=True, exist_ok=True)
            input_path = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8] + '.json')
            # Exclusive creation keeps prior captures immutable; private squad data stays local.
            descriptor = os.open(input_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(bundle, stream)
        print(f'Frozen inputs: {input_path}', file=sys.stderr)
        if args.capture_only:
            return
        result = compare_frozen_inputs(bundle, progress=lambda variant: print(f'Comparing {variant}…', file=sys.stderr))
    except Exception as exc:
        print(f'Comparison failed ({type(exc).__name__}). Check inputs, local configuration and CBC; no FPL changes submitted.', file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
