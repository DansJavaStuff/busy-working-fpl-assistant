"""Audit all captured weeks; optionally compare frozen FPL estimates to checked results."""
import argparse
import json
from pathlib import Path
import sqlite3

from snapshot_evaluation import CHECKPOINTS, DEFAULT_DB_PATH, OfficialOutcomes, snapshot_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument('--season', help='For example 2026-27; default audits every stored season')
    parser.add_argument('--checkpoint', choices=['latest', *CHECKPOINTS], default='latest')
    parser.add_argument('--fetch-outcomes', action='store_true',
                        help='Read public FPL results for finished, data-checked weeks; no writes')
    parser.add_argument('--summary', action='store_true', help='Omit individual checkpoint records and show owned-player metrics only')
    args = parser.parse_args()
    try:
        # Validate the local database before doing optional network work.
        report = snapshot_report(args.db, season=args.season, checkpoint=args.checkpoint)
        if args.fetch_outcomes:
            report = snapshot_report(args.db, season=args.season, checkpoint=args.checkpoint,
                                     outcome_loader=OfficialOutcomes())
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        parser.exit(1, f'Cannot review snapshots: {type(exc).__name__}; check database/schema or public FPL availability.\n')
    if args.summary:
        for week in report['weeks']:
            selected = next((s for s in week['snapshots'] if s['snapshot_id'] == week['selected_snapshot_id']), None)
            week['selected_capture'] = ({k:selected[k] for k in ('checkpoint','captured_at','timing')}
                                        if selected else None)
            week['invalid_snapshots'] = [{'snapshot_id':s['snapshot_id'], 'issues':s['issues']}
                                         for s in week.pop('snapshots') if not s['eligible']]
            if 'evaluation' in week:
                cohorts = week['evaluation'].pop('cohorts')
                week['evaluation']['owned_player_error'] = cohorts['owned_players']
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
