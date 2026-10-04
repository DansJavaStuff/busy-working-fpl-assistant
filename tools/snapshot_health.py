"""Read collector heartbeat and latest Gameweek snapshots without writes or API calls."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from snapshot_collector import CHECKPOINTS, CHECKPOINT_TOLERANCE_SECONDS

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data/runtime/fpl_history.db"
TARGETS = {"baseline": 3600, **dict(CHECKPOINTS)}


def utc_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def snapshot_health(db_path=DEFAULT_DB_PATH, now=None):
    now = now or datetime.now(timezone.utc)
    connection = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        state = connection.execute(
            "SELECT checked_at, status, gameweek FROM collector_state "
            "WHERE collector_name = 'predeadline'"
        ).fetchone()
        heartbeat = {"health": "missing"}
        if state:
            age = (now - utc_time(state["checked_at"])).total_seconds()
            heartbeat = {
                **dict(state), "age_seconds": age,
                "health": "clock_ahead" if age < 0 else "stale" if age > 600
                else "error" if state["status"] in (
                    "error", "deadline_passed_during_collection"
                ) else "recent",
            }
        gameweek = connection.execute("""
            SELECT g.id, s.season_key, g.gameweek, g.deadline_time
            FROM gameweeks g JOIN seasons s ON s.id = g.season_id
            WHERE g.deadline_time IS NOT NULL AND g.deadline_time != ''
            ORDER BY s.season_key DESC, g.gameweek DESC LIMIT 1
        """).fetchone()
        groups = {}
        if gameweek:
            for row in connection.execute("""
                SELECT entry_id, snapshot_type, captured_at, payload_json
                FROM snapshots WHERE gameweek_id = ? AND source = 'official_fpl_live'
                AND snapshot_type LIKE 'pre_deadline_%' ORDER BY captured_at
            """, (gameweek["id"],)):
                checkpoint = row["snapshot_type"].removeprefix("pre_deadline_")
                if checkpoint not in TARGETS:
                    continue
                payload = json.loads(row["payload_json"])
                deadline = utc_time(payload.get("deadline") or gameweek["deadline_time"])
                remaining = (deadline - utc_time(row["captured_at"])).total_seconds()
                target = TARGETS[checkpoint]
                timing = "after_deadline" if remaining <= 0 else (
                    "on_time" if (remaining > target if checkpoint == "baseline"
                                   else target - CHECKPOINT_TOLERANCE_SECONDS <= remaining <= target)
                    else "outside_window"
                )
                complete = (
                    isinstance(payload.get("bootstrap"), dict)
                    and bool(payload["bootstrap"].get("elements"))
                    and bool(payload["bootstrap"].get("events"))
                    and isinstance(payload.get("fixtures"), list)
                    and bool(payload["fixtures"])
                    and isinstance(payload.get("current_team"), dict)
                    and bool(payload["current_team"].get("picks"))
                    and isinstance(payload.get("entry"), dict)
                    and bool(payload["entry"])
                )
                groups.setdefault(row["entry_id"], {}).setdefault(checkpoint, []).append({
                    "captured_at": row["captured_at"], "seconds_remaining": remaining,
                    "timing": timing, "required_data_present": complete,
                })
        coverage = []
        if gameweek:
            remaining = (utc_time(gameweek["deadline_time"]) - now).total_seconds()
            for group in groups.values() or [{}]:
                coverage.append({
                    label: {"status": "saved", "snapshots": group[label]} if label in group
                    else {"status": "pending" if remaining > target else "missing"}
                    for label, target in TARGETS.items()
                })
        return {
            "note": "Recent heartbeat does not prove the timer is enabled. "
                    "Timing is recomputed at capture; data presence does not prove model accuracy. "
                    "Baseline can still be collected while more than an hour remains.",
            "collector": heartbeat,
            "latest_gameweek": {key: gameweek[key] for key in (
                "season_key", "gameweek", "deadline_time"
            )} if gameweek else None,
            "coverage_by_entry": coverage,
        }
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    try:
        result = snapshot_health(args.db)
    except (sqlite3.Error, ValueError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Cannot read snapshot health: {type(exc).__name__}; check database/schema/timestamps.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
