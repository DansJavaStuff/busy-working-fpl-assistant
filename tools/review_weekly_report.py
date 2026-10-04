"""Print a compact offline review of the saved planner advice."""

import argparse
import json
from pathlib import Path

from report_review import weekly_report_review

DEFAULT_REPORT = Path(__file__).resolve().parents[1] / 'data/weekly_report.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding='utf-8'))
        result = weekly_report_review(report)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        parser.exit(1, 'Cannot review saved report. Open Gameweek HQ and refresh analysis first.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
