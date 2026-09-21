from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json

from fpl_api import (
    ENTRY_ID,
    get_bootstrap,
    get_entry_picks,
    get_entry_transfers,
    get_gameweek_live,
)

HISTORY_DIR = Path("data/gameweek_history")
UK_TIMEZONE = ZoneInfo("Europe/London")


def gameweek_dir(gameweek):
    return HISTORY_DIR / f"gw{int(gameweek)}"


def load_json(path):
    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None


def load_archived_report(gameweek):
    return load_json(
        gameweek_dir(gameweek)
        / "pre_deadline_report.json"
    )


def load_submitted_plan(gameweek):
    return load_json(
        gameweek_dir(gameweek)
        / "submitted_plan.json"
    )


def load_gameweek_results(gameweek):
    return load_json(
        gameweek_dir(gameweek)
        / "results.json"
    )


def archive_pre_deadline_plan(
    report,
    plan,
):
    gameweek = int(
        report["gameweek"]
    )

    directory = gameweek_dir(
        gameweek
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        directory
        / "pre_deadline_report.json"
    )

    plan_path = (
        directory
        / "submitted_plan.json"
    )

    if not report_path.exists():
        report_path.write_text(
            json.dumps(
                report,
                indent=2,
            ),
            encoding="utf-8",
        )

    if not plan_path.exists():
        plan_path.write_text(
            json.dumps(
                plan,
                indent=2,
            ),
            encoding="utf-8",
        )


def list_archived_gameweeks():
    if not HISTORY_DIR.exists():
        return []

    gameweeks = []

    for path in HISTORY_DIR.glob("gw*"):
        if not path.is_dir():
            continue

        try:
            gameweek = int(
                path.name.removeprefix("gw")
            )
        except ValueError:
            continue

        gameweeks.append(gameweek)

    return sorted(
        gameweeks,
        reverse=True,
    )


def _event_info(gameweek):
    bootstrap = get_bootstrap()

    event = next(
        (
            event
            for event in bootstrap["events"]
            if event["id"] == gameweek
        ),
        None,
    )

    if event is None:
        raise RuntimeError(
            f"Unable to find FPL GW{gameweek}"
        )

    return event


def _archived_players(report):
    players = {}

    sources = [
        report.get(
            "current_starters",
            [],
        ),
        report.get(
            "current_bench",
            [],
        ),
        report.get(
            "starters",
            [],
        ),
        report.get(
            "bench",
            [],
        ),
        report.get(
            "recommended",
            {},
        ).get(
            "squad",
            [],
        ),
        report.get(
            "recommended",
            {},
        ).get(
            "incoming",
            [],
        ),
        report.get(
            "recommended",
            {},
        ).get(
            "outgoing",
            [],
        ),
    ]

    for source in sources:
        for player in source:
            player_id = player.get("id")
            if player_id is not None:
                players[player_id] = player

    return players


def _projection(player, gameweek):
    if not player:
        return None

    value = player.get(
        f"proj_gw{gameweek}"
    )

    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _format_player_result(
    player_id,
    role,
    archived_players,
    live_points,
    official_pick,
    gameweek,
    captain_id,
    vice_id,
):
    archived = archived_players.get(
        player_id,
        {},
    )

    raw_actual = live_points.get(
        player_id,
        0,
    )

    multiplier = (
        official_pick.get(
            "multiplier",
            0,
        )
        if official_pick
        else 0
    )

    projected = _projection(
        archived,
        gameweek,
    )

    actual_contribution = (
        raw_actual * multiplier
    )

    projection_delta = (
        raw_actual - projected
        if projected is not None
        else None
    )

    return {
        "id":
            player_id,
        "name":
            archived.get(
                "name",
                str(player_id),
            ),
        "team":
            archived.get(
                "team",
                "",
            ),
        "position":
            archived.get(
                "position",
                "",
            ),
        "role":
            role,
        "projected":
            projected,
        "actual_points":
            raw_actual,
        "multiplier":
            multiplier,
        "actual_contribution":
            actual_contribution,
        "projection_delta":
            projection_delta,
        "captain":
            player_id == captain_id,
        "vice_captain":
            player_id == vice_id,
    }


def collect_gameweek_results(
    gameweek,
    entry_id=ENTRY_ID,
):
    gameweek = int(gameweek)

    directory = gameweek_dir(
        gameweek
    )

    report = load_archived_report(
        gameweek
    )
    plan = load_submitted_plan(
        gameweek
    )

    if report is None:
        raise RuntimeError(
            "Missing pre-deadline report for "
            f"GW{gameweek}."
        )

    if plan is None:
        raise RuntimeError(
            "Missing submitted plan for "
            f"GW{gameweek}."
        )

    bootstrap = get_bootstrap()

    bootstrap_players = {
        player["id"]: player
        for player in bootstrap.get(
            "elements",
            [],
        )
    }

    event = next(
        (
            event
            for event in bootstrap["events"]
            if event["id"] == gameweek
        ),
        None,
    )

    if event is None:
        raise RuntimeError(
            f"Unable to find FPL GW{gameweek}"
        )

    live = get_gameweek_live(
        gameweek
    )

    live_points = {
        element["id"]:
            element.get(
                "stats",
                {},
            ).get(
                "total_points",
                0,
            )
        for element in live.get(
            "elements",
            [],
        )
    }

    entry = get_entry_picks(
        gameweek,
        entry_id=entry_id,
    )

    official_picks = {
        pick["element"]: pick
        for pick in entry.get(
            "picks",
            [],
        )
    }

    archived_players = (
        _archived_players(
            report
        )
    )

    captain_id = plan.get(
        "captain_id"
    )
    vice_id = plan.get(
        "vice_id"
    )

    starters = []
    bench = []

    for player in plan.get(
        "starters",
        [],
    ):
        player_id = player["id"]

        starters.append(
            _format_player_result(
                player_id,
                "starter",
                archived_players,
                live_points,
                official_picks.get(
                    player_id
                ),
                gameweek,
                captain_id,
                vice_id,
            )
        )

    for index, player in enumerate(
        plan.get(
            "bench",
            [],
        ),
        start=1,
    ):
        player_id = player["id"]

        bench.append(
            _format_player_result(
                player_id,
                f"bench_{index}",
                archived_players,
                live_points,
                official_picks.get(
                    player_id
                ),
                gameweek,
                captain_id,
                vice_id,
            )
        )

    projected_xi = sum(
        player["projected"] or 0
        for player in starters
    )

    captain_projection = next(
        (
            player["projected"]
            for player in starters
            if player["captain"]
        ),
        0,
    ) or 0

    projected_gross = (
        projected_xi
        + captain_projection
    )

    hit_cost = int(
        plan.get(
            "hit_cost",
            0,
        )
        or 0
    )

    projected_net = (
        projected_gross
        - hit_cost
    )

    entry_history = entry.get(
        "entry_history",
        {},
    )

    actual_official = (
        entry_history.get(
            "points"
        )
    )

    if actual_official is None:
        actual_official = sum(
            player[
                "actual_contribution"
            ]
            for player in (
                starters + bench
            )
        )

    planned_transfers = list(
        plan.get(
            "transfers",
            [],
        )
    )

    transfer_source = (
        "submitted_plan"
    )

    if not planned_transfers:

        entry_transfers = (
            get_entry_transfers(
                entry_id=entry_id,
            )
        )

        planned_transfers = [
            {
                "element_out":
                    transfer[
                        "element_out"
                    ],
                "element_out_name":
                    bootstrap_players.get(
                        transfer[
                            "element_out"
                        ],
                        {},
                    ).get(
                        "web_name",
                        str(
                            transfer[
                                "element_out"
                            ]
                        ),
                    ),
                "element_in":
                    transfer[
                        "element_in"
                    ],
                "element_in_name":
                    bootstrap_players.get(
                        transfer[
                            "element_in"
                        ],
                        {},
                    ).get(
                        "web_name",
                        str(
                            transfer[
                                "element_in"
                            ]
                        ),
                    ),
            }
            for transfer
            in entry_transfers
            if transfer.get(
                "event"
            ) == gameweek
        ]

        if planned_transfers:
            transfer_source = (
                "fpl_entry_history"
            )

    transfers = []

    for transfer in planned_transfers:
        outgoing_id = transfer[
            "element_out"
        ]
        incoming_id = transfer[
            "element_in"
        ]

        outgoing = (
            archived_players.get(
                outgoing_id,
                {},
            )
        )
        incoming = (
            archived_players.get(
                incoming_id,
                {},
            )
        )

        outgoing_projection = (
            _projection(
                outgoing,
                gameweek,
            )
        )
        incoming_projection = (
            _projection(
                incoming,
                gameweek,
            )
        )

        outgoing_actual = (
            live_points.get(
                outgoing_id,
                0,
            )
        )
        incoming_actual = (
            live_points.get(
                incoming_id,
                0,
            )
        )

        expected_edge = None

        if (
            outgoing_projection
            is not None
            and
            incoming_projection
            is not None
        ):
            expected_edge = (
                incoming_projection
                - outgoing_projection
            )

        transfers.append({
            "out_id":
                outgoing_id,
            "out_name":
                transfer.get(
                    "element_out_name",
                    outgoing.get(
                        "name",
                        str(outgoing_id),
                    ),
                ),
            "out_projected":
                outgoing_projection,
            "out_actual":
                outgoing_actual,
            "in_id":
                incoming_id,
            "in_name":
                transfer.get(
                    "element_in_name",
                    incoming.get(
                        "name",
                        str(incoming_id),
                    ),
                ),
            "in_projected":
                incoming_projection,
            "in_actual":
                incoming_actual,
            "expected_edge":
                expected_edge,
            "actual_edge":
                (
                    incoming_actual
                    - outgoing_actual
                ),
        })

    transfer_actual_gain = sum(
        transfer["actual_edge"]
        for transfer in transfers
    )

    transfer_expected_gain = sum(
        transfer["expected_edge"] or 0
        for transfer in transfers
    )

    result = {
        "schema_version":
            1,
        "gameweek":
            gameweek,
        "collected_at":
            datetime.now(
                UK_TIMEZONE
            ).isoformat(),
        "event_finished":
            bool(
                event.get(
                    "finished"
                )
            ),
        "average_points":
            event.get(
                "average_entry_score"
            ),
        "highest_points":
            event.get(
                "highest_score"
            ),
        "entry_history":
            {
                "points":
                    actual_official,
                "total_points":
                    entry_history.get(
                        "total_points"
                    ),
                "rank":
                    entry_history.get(
                        "rank"
                    ),
                "overall_rank":
                    entry_history.get(
                        "overall_rank"
                    ),
                "transfers":
                    entry_history.get(
                        "event_transfers"
                    ),
                "transfer_cost":
                    entry_history.get(
                        "event_transfers_cost",
                        hit_cost,
                    ),
                "points_on_bench":
                    entry_history.get(
                        "points_on_bench"
                    ),
            },
        "projection":
            {
                "gross":
                    projected_gross,
                "hit_cost":
                    hit_cost,
                "net":
                    projected_net,
                "actual":
                    actual_official,
                "difference":
                    (
                        actual_official
                        - projected_net
                    ),
            },
        "players":
            starters + bench,
        "starters":
            starters,
        "bench":
            bench,
        "transfers":
            transfers,
        "transfer_source":
            transfer_source,
        "transfer_summary":
            {
                "expected_gain":
                    transfer_expected_gain,
                "actual_gain":
                    transfer_actual_gain,
                "hit_cost":
                    hit_cost,
                "net_actual_gain":
                    (
                        transfer_actual_gain
                        - hit_cost
                    ),
            },
        "automatic_subs":
            entry.get(
                "automatic_subs",
                [],
            ),
        "active_chip":
            entry.get(
                "active_chip",
            ),
    }

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        directory
        / "results.json"
    ).write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    return result


def load_history():
    history = []

    for gameweek in (
        list_archived_gameweeks()
    ):
        history.append({
            "gameweek":
                gameweek,
            "report":
                load_archived_report(
                    gameweek
                ),
            "plan":
                load_submitted_plan(
                    gameweek
                ),
            "results":
                load_gameweek_results(
                    gameweek
                ),
        })

    return history
