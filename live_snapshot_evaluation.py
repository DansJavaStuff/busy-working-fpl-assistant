from statistics import mean


MINIMUM_REVIEW_GAMEWEEKS = 5


def _rounded_mean(values):
    if not values:
        return None

    return round(
        mean(values),
        2,
    )


def _captain_metrics(starters):
    if not starters:
        return {
            "captain": None,
            "captain_points": None,
            "best_starter": None,
            "best_starter_points": None,
            "hindsight_gap": None,
        }

    captain = next(
        (
            player
            for player in starters
            if player.get("captain")
        ),
        None,
    )
    best = max(
        starters,
        key=lambda player:
            float(
                player.get(
                    "actual_points",
                    0,
                )
                or 0
            ),
    )

    if captain is None:
        return {
            "captain": None,
            "captain_points": None,
            "best_starter":
                best.get("name"),
            "best_starter_points":
                float(
                    best.get(
                        "actual_points",
                        0,
                    )
                    or 0
                ),
            "hindsight_gap": None,
        }

    captain_points = float(
        captain.get(
            "actual_points",
            0,
        )
        or 0
    )
    best_points = float(
        best.get(
            "actual_points",
            0,
        )
        or 0
    )

    return {
        "captain":
            captain.get("name"),
        "captain_points":
            captain_points,
        "best_starter":
            best.get("name"),
        "best_starter_points":
            best_points,
        "hindsight_gap":
            best_points
            - captain_points,
    }


def evaluate_live_snapshot_history(
    history,
):
    rows = []
    missing_results = []
    unfinished_results = []

    for item in sorted(
        history,
        key=lambda row:
            int(row["gameweek"]),
    ):
        gameweek = int(
            item["gameweek"]
        )
        result = item.get("results")

        if result is None:
            missing_results.append(
                gameweek
            )
            continue

        if not result.get(
            "event_finished",
            False,
        ):
            unfinished_results.append(
                gameweek
            )
            continue

        projection = result.get(
            "projection",
            {},
        )
        projected = projection.get("net")
        actual = projection.get("actual")

        if (
            projected is None
            or actual is None
        ):
            missing_results.append(
                gameweek
            )
            continue

        projected = float(projected)
        actual = float(actual)
        error = projected - actual
        transfers = result.get(
            "transfers",
            [],
        )
        transfer = result.get(
            "transfer_summary",
            {},
        )
        transfer_source = result.get(
            "transfer_source",
            "submitted_plan",
        )
        captain = _captain_metrics(
            result.get(
                "starters",
                [],
            )
        )

        rows.append({
            "gameweek": gameweek,
            "projected":
                round(projected, 2),
            "actual":
                round(actual, 2),
            "error":
                round(error, 2),
            "absolute_error":
                round(abs(error), 2),
            "average_points":
                result.get(
                    "average_points"
                ),
            "points_on_bench":
                (
                    result.get(
                        "entry_history",
                        {},
                    ).get(
                        "points_on_bench"
                    )
                ),
            "transfer_count":
                len(transfers),
            "transfer_source":
                transfer_source,
            "transfer_expected_gain":
                float(
                    transfer.get(
                        "expected_gain",
                        0,
                    )
                    or 0
                ),
            "transfer_actual_gain":
                float(
                    transfer.get(
                        "actual_gain",
                        0,
                    )
                    or 0
                ),
            "transfer_net_actual_gain":
                float(
                    transfer.get(
                        "net_actual_gain",
                        0,
                    )
                    or 0
                ),
            **captain,
        })

    errors = [
        row["error"]
        for row in rows
    ]
    transfer_rows = [
        row
        for row in rows
        if row["transfer_count"] > 0
        and row["transfer_source"]
        == "submitted_plan"
    ]
    unmatched_transfer_rows = [
        row
        for row in rows
        if row["transfer_count"] > 0
        and row["transfer_source"]
        != "submitted_plan"
    ]
    hold_rows = [
        row
        for row in rows
        if row["transfer_count"] == 0
        and row["transfer_source"]
        == "submitted_plan"
    ]
    captain_rows = [
        row
        for row in rows
        if row["captain_points"]
        is not None
    ]
    bench_points = [
        float(row["points_on_bench"])
        for row in rows
        if row["points_on_bench"]
        is not None
    ]
    completed = len(rows)

    return {
        "completed_gameweeks":
            completed,
        "minimum_review_gameweeks":
            MINIMUM_REVIEW_GAMEWEEKS,
        "ready_for_review":
            completed
            >= MINIMUM_REVIEW_GAMEWEEKS,
        "missing_result_gameweeks":
            missing_results,
        "unfinished_gameweeks":
            unfinished_results,
        "projection": {
            "projected_mean":
                _rounded_mean([
                    row["projected"]
                    for row in rows
                ]),
            "actual_mean":
                _rounded_mean([
                    row["actual"]
                    for row in rows
                ]),
            "mean_error":
                _rounded_mean(errors),
            "mean_absolute_error":
                _rounded_mean([
                    abs(error)
                    for error in errors
                ]),
        },
        "transfers": {
            "hold_gameweeks":
                len(hold_rows),
            "transfer_gameweeks":
                len(transfer_rows),
            "unmatched_execution_gameweeks":
                len(unmatched_transfer_rows),
            "expected_gain_mean":
                _rounded_mean([
                    row[
                        "transfer_expected_gain"
                    ]
                    for row in transfer_rows
                ]),
            "actual_gain_mean":
                _rounded_mean([
                    row[
                        "transfer_actual_gain"
                    ]
                    for row in transfer_rows
                ]),
            "net_actual_gain_mean":
                _rounded_mean([
                    row[
                        "transfer_net_actual_gain"
                    ]
                    for row in transfer_rows
                ]),
            "positive_net_gameweeks":
                sum(
                    1
                    for row in transfer_rows
                    if row[
                        "transfer_net_actual_gain"
                    ] > 0
                ),
        },
        "captain": {
            "captain_points_mean":
                _rounded_mean([
                    row["captain_points"]
                    for row in captain_rows
                ]),
            "best_starter_points_mean":
                _rounded_mean([
                    row[
                        "best_starter_points"
                    ]
                    for row in captain_rows
                ]),
            "hindsight_gap_mean":
                _rounded_mean([
                    row["hindsight_gap"]
                    for row in captain_rows
                ]),
        },
        "lineup": {
            "bench_points_mean":
                _rounded_mean(
                    bench_points
                ),
        },
        "gameweeks":
            rows,
    }
