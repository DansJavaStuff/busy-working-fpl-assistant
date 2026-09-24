from history_store import (
    record_collector_state,
)
from snapshot_collector import (
    collect_if_due,
)


def main():
    try:
        result = collect_if_due()
    except Exception as exc:
        record_collector_state(
            "error",
            message=str(exc)[:500],
        )
        raise

    record_collector_state(
        result["status"],
        gameweek=result.get(
            "gameweek"
        ),
        seconds_remaining=result.get(
            "seconds_remaining"
        ),
        message=result.get(
            "checkpoint"
        ),
    )

    status = result["status"]
    gameweek = result["gameweek"]

    if status == "saved":
        timing = (
            ""
            if result.get(
                "on_time",
                True,
            )
            else (
                " (late by "
                f"{result.get('late_by_seconds', 0)}s)"
            )
        )
        print(
            f"Saved GW{gameweek} "
            f"{result['checkpoint']} "
            "pre-deadline snapshot"
            f"{timing}."
        )
        return

    if status == "already_saved":
        print(
            f"GW{gameweek} "
            f"{result['checkpoint']} "
            "snapshot already exists."
        )
        return

    if status == "locked":
        print(
            f"GW{gameweek} deadline "
            "has already passed."
        )
        return

    print(
        f"No GW{gameweek} snapshot "
        "checkpoint is due yet."
    )


if __name__ == "__main__":
    main()
