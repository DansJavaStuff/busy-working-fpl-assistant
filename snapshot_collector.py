from datetime import datetime, timezone

from fpl_api import (
    get_bootstrap,
    get_entry,
    get_fixtures,
    get_gameweek_deadline,
    get_my_team,
    get_planning_gameweek,
)
from history_store import (
    save_snapshot,
    snapshot_exists,
    upsert_gameweek,
    upsert_season,
)
from local_config import get_entry_id


CHECKPOINTS = (
    ("t60m", 60 * 60),
    ("t15m", 15 * 60),
    ("t10m", 10 * 60),
    ("t5m", 5 * 60),
)

CHECKPOINT_TOLERANCE_SECONDS = (
    3 * 60
)

CHECKPOINT_WINDOWS = (
    ("t60m", 60 * 60, 15 * 60),
    ("t15m", 15 * 60, 10 * 60),
    ("t10m", 10 * 60, 5 * 60),
    ("t5m", 5 * 60, 0),
)


def _season_from_bootstrap(
    bootstrap,
):
    events = bootstrap.get(
        "events",
        [],
    )

    deadline_text = next(
        (
            event.get(
                "deadline_time"
            )
            for event in events
            if event.get(
                "deadline_time"
            )
        ),
        None,
    )

    if not deadline_text:
        raise RuntimeError(
            "Unable to derive season "
            "from FPL bootstrap data."
        )

    start_year = (
        datetime.fromisoformat(
            deadline_text.replace(
                "Z",
                "+00:00",
            )
        ).year
    )

    return {
        "season_key":
            f"{start_year}-"
            f"{str(start_year + 1)[-2:]}",
        "starts_year":
            start_year,
        "ends_year":
            start_year + 1,
    }


def checkpoint_details_for_seconds(
    seconds_remaining,
):
    if seconds_remaining <= 0:
        return None

    if seconds_remaining > 60 * 60:
        return {
            "label": "baseline",
            "target_seconds": None,
            "late_by_seconds": 0,
            "on_time": True,
        }

    for (
        label,
        target_seconds,
        window_floor,
    ) in CHECKPOINT_WINDOWS:
        if (
            seconds_remaining
            <= target_seconds
            and
            seconds_remaining
            > window_floor
        ):
            late_by = max(
                0,
                target_seconds
                - seconds_remaining,
            )

            return {
                "label": label,
                "target_seconds":
                    target_seconds,
                "late_by_seconds":
                    late_by,
                "on_time":
                    late_by
                    <= CHECKPOINT_TOLERANCE_SECONDS,
            }

    return None


def checkpoint_for_seconds(
    seconds_remaining,
):
    details = (
        checkpoint_details_for_seconds(
            seconds_remaining
        )
    )

    return (
        details["label"]
        if details
        else None
    )


def _snapshot_type(
    checkpoint,
):
    return (
        "pre_deadline_"
        f"{checkpoint}"
    )


def collect_if_due():
    planning_gameweek = (
        get_planning_gameweek()
    )

    deadline = (
        get_gameweek_deadline(
            planning_gameweek
        )
    )

    if deadline["locked"]:
        return {
            "status": "locked",
            "gameweek":
                planning_gameweek,
            "seconds_remaining":
                0,
        }

    checkpoint_details = (
        checkpoint_details_for_seconds(
            deadline[
                "seconds_remaining"
            ]
        )
    )

    checkpoint = (
        checkpoint_details["label"]
        if checkpoint_details
        else None
    )

    if checkpoint is None:
        return {
            "status": "not_due",
            "gameweek":
                planning_gameweek,
            "seconds_remaining":
                deadline[
                    "seconds_remaining"
                ],
        }

    entry_id = get_entry_id()

    bootstrap = get_bootstrap()

    season = _season_from_bootstrap(
        bootstrap
    )

    season_id = upsert_season(
        season["season_key"],
        season["starts_year"],
        season["ends_year"],
        source="official_fpl",
    )

    gameweek_id = upsert_gameweek(
        season_id,
        planning_gameweek,
        deadline_time=
            deadline["deadline_iso"],
    )

    snapshot_type = (
        _snapshot_type(
            checkpoint
        )
    )

    if snapshot_exists(
        season_id,
        gameweek_id,
        snapshot_type,
        entry_id=entry_id,
    ):
        return {
            "status": "already_saved",
            "gameweek":
                planning_gameweek,
            "checkpoint":
                checkpoint,
            "snapshot_type":
                snapshot_type,
            "seconds_remaining":
                deadline[
                    "seconds_remaining"
                ],
        }

    bootstrap = get_bootstrap(
        force_refresh=True,
        allow_stale=False,
    )

    fixtures = get_fixtures(
        force_refresh=True,
        allow_stale=False,
    )

    current_team = get_my_team(
        entry_id=entry_id,
    )

    entry = get_entry(
        entry_id=entry_id,
    )

    captured_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    payload = {
        "checkpoint":
            checkpoint,
        "captured_at":
            captured_at,
        "deadline":
            deadline[
                "deadline_iso"
            ],
        "seconds_remaining":
            deadline[
                "seconds_remaining"
            ],
        "target_seconds_remaining":
            checkpoint_details.get(
                "target_seconds"
            ),
        "late_by_seconds":
            checkpoint_details.get(
                "late_by_seconds",
                0,
            ),
        "on_time":
            checkpoint_details.get(
                "on_time",
                True,
            ),
        "bootstrap":
            bootstrap,
        "fixtures":
            fixtures,
        "current_team":
            current_team,
        "entry":
            entry,
    }

    snapshot_id = save_snapshot(
        season_id,
        gameweek_id,
        snapshot_type,
        payload,
        entry_id=entry_id,
        captured_at=captured_at,
        source="official_fpl_live",
    )

    return {
        "status": "saved",
        "snapshot_id":
            snapshot_id,
        "gameweek":
            planning_gameweek,
        "checkpoint":
            checkpoint,
        "snapshot_type":
            snapshot_type,
        "seconds_remaining":
            deadline[
                "seconds_remaining"
            ],
        "late_by_seconds":
            checkpoint_details.get(
                "late_by_seconds",
                0,
            ),
        "on_time":
            checkpoint_details.get(
                "on_time",
                True,
            ),
    }
