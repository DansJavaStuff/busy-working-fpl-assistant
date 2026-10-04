from gameweek_history import load_history
from live_snapshot_evaluation import (
    evaluate_live_snapshot_history,
)


def _value(value):
    return (
        "n/a"
        if value is None
        else value
    )


def main():
    report = (
        evaluate_live_snapshot_history(
            load_history()
        )
    )

    print(
        "Live pre-deadline recommendation evaluation"
    )
    print(
        "Completed Gameweeks:",
        report["completed_gameweeks"],
    )
    print(
        "Review status:",
        (
            "READY"
            if report["ready_for_review"]
            else (
                "COLLECTING "
                f"({report['completed_gameweeks']}/"
                f"{report['minimum_review_gameweeks']})"
            )
        ),
    )

    if report["missing_result_gameweeks"]:
        print(
            "Missing results:",
            ", ".join(
                f"GW{gameweek}"
                for gameweek in report[
                    "missing_result_gameweeks"
                ]
            ),
        )

    if report["unfinished_gameweeks"]:
        print(
            "Unfinished:",
            ", ".join(
                f"GW{gameweek}"
                for gameweek in report[
                    "unfinished_gameweeks"
                ]
            ),
        )

    projection = report["projection"]
    print("Projection:")
    print(
        "  Mean projected / actual:",
        f"{_value(projection['projected_mean'])} / "
        f"{_value(projection['actual_mean'])}",
    )
    print(
        "  Mean error / MAE:",
        f"{_value(projection['mean_error'])} / "
        f"{_value(projection['mean_absolute_error'])}",
    )

    transfers = report["transfers"]
    print("Transfers:")
    print(
        "  HOLD / transfer Gameweeks:",
        f"{transfers['hold_gameweeks']} / "
        f"{transfers['transfer_gameweeks']}",
    )
    print(
        "  Unmatched execution Gameweeks:",
        transfers[
            "unmatched_execution_gameweeks"
        ],
    )
    print(
        "  Mean expected / actual / net gain:",
        f"{_value(transfers['expected_gain_mean'])} / "
        f"{_value(transfers['actual_gain_mean'])} / "
        f"{_value(transfers['net_actual_gain_mean'])}",
    )
    print(
        "  Positive net transfer Gameweeks:",
        transfers["positive_net_gameweeks"],
    )

    captain = report["captain"]
    print("Captain:")
    print(
        "  Mean captain / best starter points:",
        f"{_value(captain['captain_points_mean'])} / "
        f"{_value(captain['best_starter_points_mean'])}",
    )
    print(
        "  Mean hindsight gap:",
        _value(
            captain["hindsight_gap_mean"]
        ),
    )
    print(
        "Lineup mean bench points:",
        _value(
            report[
                "lineup"
            ]["bench_points_mean"]
        ),
    )

    print("Gameweeks:")
    for row in report["gameweeks"]:
        transfer_text = "HOLD"

        if (
            row["transfer_count"]
            and row["transfer_source"]
            == "submitted_plan"
        ):
            transfer_text = (
                f"{row['transfer_count']} transfer(s), "
                "net "
                f"{row['transfer_net_actual_gain']:+.1f}"
            )
        elif row["transfer_count"]:
            transfer_text = (
                "UNMATCHED EXECUTION "
                f"({row['transfer_count']} transfer(s))"
            )

        print(
            f"  GW{row['gameweek']}: "
            f"projected {row['projected']:.2f} · "
            f"actual {row['actual']:.0f} · "
            f"error {row['error']:+.2f} · "
            f"{transfer_text} · "
            f"captain {row['captain']} "
            f"{_value(row['captain_points'])}pts · "
            f"bench {_value(row['points_on_bench'])}pts"
        )

    if not report["ready_for_review"]:
        print(
            "HOLD: fewer than five completed live "
            "Gameweeks; do not retune thresholds yet."
        )


if __name__ == "__main__":
    main()
