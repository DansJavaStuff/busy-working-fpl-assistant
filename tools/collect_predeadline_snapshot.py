from snapshot_collector import (
    collect_if_due,
)


def main():
    result = collect_if_due()

    status = result["status"]
    gameweek = result["gameweek"]

    if status == "saved":
        print(
            f"Saved GW{gameweek} "
            f"{result['checkpoint']} "
            "pre-deadline snapshot."
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
