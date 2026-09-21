import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from gameweek_history import (
    collect_gameweek_results,
)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: "
            "python3 tools/"
            "collect_gameweek_results.py "
            "<gameweek>"
        )

    gameweek = int(
        sys.argv[1]
    )

    result = (
        collect_gameweek_results(
            gameweek
        )
    )

    projection = result[
        "projection"
    ]
    transfer = result[
        "transfer_summary"
    ]

    print(
        f"GW{gameweek} results collected"
    )
    print(
        "Finished:",
        result[
            "event_finished"
        ],
    )
    print(
        "Projected:",
        f"{projection['net']:.2f}",
    )
    print(
        "Actual:",
        projection["actual"],
    )
    print(
        "Difference:",
        f"{projection['difference']:+.2f}",
    )
    print(
        "Transfer actual gain:",
        f"{transfer['actual_gain']:+.0f}",
    )
    print(
        "Transfer net gain:",
        f"{transfer['net_actual_gain']:+.0f}",
    )


if __name__ == "__main__":
    main()
