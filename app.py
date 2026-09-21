REPORT_SCHEMA_VERSION = 4

from fpl_api import (
    get_my_team,
    get_planning_gameweek,
    get_gameweek_deadline
)

from optimizer import load_players

from transfer_optimizer import (
    optimise_transfers,
    MINIMUM_FREE_TRANSFER_GAIN,
    MINIMUM_PAID_TRANSFER_GAIN,
)

from tools.apply_approved_plan import (
    apply_approved_plan,
    PlanApplyError,
)

from gameweek_history import (
    archive_pre_deadline_plan,
    collect_gameweek_results,
    load_history,
)

import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
)

app = Flask(__name__)

APPROVAL_FILE = Path(
    "data/weekly_approval.json"
)
RECOMMENDATION_FILE = Path(
    "data/weekly_recommendation.json"
)
REPORT_FILE = Path(
    "data/weekly_report.json"
)
UK_TIMEZONE = ZoneInfo(
    "Europe/London"
)

def load_approval():

    if not APPROVAL_FILE.exists():
        return None

    with open(
        APPROVAL_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_approval(data):

    APPROVAL_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        APPROVAL_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
        )

def clear_approval():

    if APPROVAL_FILE.exists():
        APPROVAL_FILE.unlink()

def pair_transfers(result):

    remaining_incoming = (
        result["incoming"].copy()
    )

    pairs = []

    for outgoing in sorted(
        result["outgoing"],
        key=lambda p: p["position_id"],
    ):

        incoming = next(
            p
            for p in remaining_incoming
            if p["position"]
            == outgoing["position"]
        )

        remaining_incoming.remove(
            incoming
        )

        pairs.append({
            "out": outgoing,
            "in": incoming,
        })

    return pairs


def build_weekly_report(
    must_keep_ids=None,
    must_include_ids=None,
):

    must_keep_ids = list(
        must_keep_ids or []
    )

    must_include_ids = list(
        must_include_ids or []
    )

    planning_gameweek = (
        get_planning_gameweek()
    )
    
    deadline_info = (
        get_gameweek_deadline(
            planning_gameweek
        )
    )

    deadline_local = (
        deadline_info["deadline"]
        .astimezone(
            UK_TIMEZONE
        )
    )

    current_team = get_my_team()

    players = load_players()

    players_by_id = {
        p["id"]: p
        for p in players
    }

    current_starters = []
    current_bench = []

    current_captain = None
    current_vice = None

    for pick in sorted(
        current_team["picks"],
        key=lambda p: p["position"],
    ):

        player = dict(
            players_by_id[
                pick["element"]
            ]
        )

        player["live_position"] = (
            pick["position"]
        )

        player["live_captain"] = (
            pick["is_captain"]
        )

        player["live_vice"] = (
            pick["is_vice_captain"]
        )

        if pick["position"] <= 11:
            current_starters.append(
                player
            )
        else:
            current_bench.append(
                player
            )

        if pick["is_captain"]:
            current_captain = player

        if pick["is_vice_captain"]:
            current_vice = player

    transfers = current_team[
        "transfers"
    ]

    free_transfers = max(
        0,
        transfers["limit"]
        - transfers["made"]
    )

    results = []

    for number_of_transfers in range(
        0,
        4
    ):

        result = optimise_transfers(
            players,
            current_team,
            planning_gameweek,
            number_of_transfers,
            must_keep_ids=
                must_keep_ids,
            must_include_ids=
                must_include_ids,
        )

        if result:
            results.append(result)

    hold = next(
        r
        for r in results
        if r["transfers"] == 0
    )

    best_overall = max(
        results,
        key=lambda r:
            r["net_score"]
    )

    best_no_hit = max(
        (
            r
            for r in results
            if r["hit_cost"] == 0
        ),
        key=lambda r:
            r["net_score"]
    )

    recommended = best_overall

    paid_transfer_gain = None

    if best_overall["hit_cost"] > 0:

        paid_transfer_gain = (
            best_overall["net_score"]
            - best_no_hit["net_score"]
        )

        if (
            paid_transfer_gain
            <
            MINIMUM_PAID_TRANSFER_GAIN
        ):
            recommended = best_no_hit

    transfer_gain = (
        recommended["net_score"]
        - hold["net_score"]
    )

    if (
        recommended["transfers"] > 0
        and
        transfer_gain
        < MINIMUM_FREE_TRANSFER_GAIN
    ):
        recommended = hold

    scenarios = []

    for result in results:

        scenarios.append({
            "transfers":
                result["transfers"],
            "score":
                result["net_score"],
            "raw_score":
                result["raw_score"],
            "hit_cost":
                result["hit_cost"],
            "gain":
                result["net_score"]
                - hold["net_score"],
            "bank_after":
                result["bank_after"] / 10,
            "pairs":
                pair_transfers(result)
                if result["transfers"]
                else [],
        })

    starters = [
        p
        for p in recommended["squad"]
        if p["starter"]
    ]

    starters.sort(
        key=lambda p: (
            p["position_id"],
            -p.get(
                f"proj_gw{planning_gameweek}",
                0
            )
        )
    )

    bench = [
        p
        for p in recommended["squad"]
        if not p["starter"]
    ]

    bench_outfield = [
        p
        for p in bench
        if p["position"] != "GKP"
    ]

    bench_goalkeepers = [
        p
        for p in bench
        if p["position"] == "GKP"
    ]

    bench_outfield.sort(
        key=lambda p:
            p.get(
                f"proj_gw{planning_gameweek}",
                0,
            ),
        reverse=True,
    )

    bench = (
        bench_outfield
        + bench_goalkeepers
    )

    captain = next(
        p
        for p in recommended["squad"]
        if p["captain"]
    )

    current_starter_ids = {
        p["id"]
        for p in current_starters
    }

    recommended_starter_ids = {
        p["id"]
        for p in starters
    }

    xi_out = [
        p
        for p in current_starters
        if p["id"]
        not in recommended_starter_ids
    ]

    xi_in = [
        p
        for p in starters
        if p["id"]
        not in current_starter_ids
    ]

    selection_changes = {
        "xi_out":
            xi_out,

        "xi_in":
            xi_in,

        "captain_changed":
            (
                current_captain
                and
                current_captain["id"]
                != captain["id"]
            ),

        "vice_changed":
            (
                current_vice
                and
                current_vice["id"]
                != recommended[
                    "vice_captain"
                ]["id"]
            ),
    }

    approval = load_approval()

    return {
        "schema_version":
            REPORT_SCHEMA_VERSION,
        "gameweek":
            planning_gameweek,
        "bank":
            transfers["bank"] / 10,
        "free_transfers":
            free_transfers,
        "hold_score":
            hold["net_score"],
        "recommended":
            recommended,
        "recommended_pairs":
            pair_transfers(recommended)
            if recommended["transfers"]
            else [],
        "transfer_gain":
            recommended["net_score"]
            - hold["net_score"],
        "paid_transfer_gain":
            paid_transfer_gain,
        "scenarios":
            scenarios,
        "current_starters":
            current_starters,
        "current_bench":
            current_bench,
        "current_captain":
            current_captain,
        "current_vice":
            current_vice,
        "starters":
            starters,
        "bench":
            bench,
        "captain":
            captain,
        "vice":
            recommended["vice_captain"],
        "selection_changes":
            selection_changes,
        "approval":
            approval,
        "deadline_iso":
            deadline_info[
                "deadline_iso"
            ],

        "deadline_display":
            deadline_local.strftime(
                "%a %d %b, %H:%M"
            ),

        "deadline_locked":
            deadline_info[
                "locked"
            ],
        "constraints": {
            "must_keep_ids":
                must_keep_ids,
            "must_include_ids":
                must_include_ids,
        },
    }

def save_recommendation_snapshot(
    report,
):

    recommendation = report[
        "recommended"
    ]

    snapshot = {
        "created_at":
            datetime.now(
                UK_TIMEZONE
            ).isoformat(),

        "gameweek":
            report[
                "gameweek"
            ],

        "model_score":
            recommendation[
                "net_score"
            ],

        "hit_cost":
            recommendation[
                "hit_cost"
            ],

        "bank_after":
            recommendation.get(
                "bank_after"
            ),

        "transfers": [],

        "source_squad_ids": [
            p["id"]
            for p in (
                report["starters"]
                + report["bench"]
            )
            if p["id"] not in {
                incoming["id"]
                for incoming
                in recommendation["incoming"]
            }
        ]
        + [
            outgoing["id"]
            for outgoing
            in recommendation["outgoing"]
        ],

        "starters": [
            {
                "id": p["id"],
                "name": p["name"],
                "position": p["position"],
            }
            for p in report["starters"]
        ],

        "bench": [
            {
                "id": p["id"],
                "name": p["name"],
                "position": p["position"],
            }
            for p in report["bench"]
        ],

        "captain_id":
            report["captain"]["id"],

        "vice_id":
            report["vice"]["id"],
    }

    remaining_incoming = (
        recommendation[
            "incoming"
        ].copy()
    )

    for outgoing in sorted(
        recommendation["outgoing"],
        key=lambda p:
            p["position_id"],
    ):

        incoming = next(
            p
            for p
            in remaining_incoming
            if p["position"]
            == outgoing["position"]
        )

        remaining_incoming.remove(
            incoming
        )

        snapshot[
            "transfers"
        ].append({
            "element_out":
                outgoing["id"],

            "element_out_name":
                outgoing["name"],

            "element_in":
                incoming["id"],

            "element_in_name":
                incoming["name"],
        })

    RECOMMENDATION_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RECOMMENDATION_FILE.write_text(
        json.dumps(
            snapshot,
            indent=2,
        )
    )

    return snapshot


def load_recommendation_snapshot():

    if not RECOMMENDATION_FILE.exists():
        return None

    return json.loads(
        RECOMMENDATION_FILE.read_text()
    )

def save_weekly_report(
    report,
):

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_weekly_report():

    if not REPORT_FILE.exists():
        return None

    try:

        report = json.loads(
            REPORT_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return None

    if (
        report.get("schema_version")
        != REPORT_SCHEMA_VERSION
    ):
        return None

    return report

def validate_proposed_team(
    report,
    starter_ids,
    bench_ids,
    captain_id,
    vice_id,
):

    if len(starter_ids) != 11:
        raise ValueError(
            "Proposal must contain 11 starters."
        )

    if len(bench_ids) != 4:
        raise ValueError(
            "Proposal must contain 4 bench players."
        )

    all_ids = (
        starter_ids
        + bench_ids
    )

    if len(all_ids) != len(set(all_ids)):
        raise ValueError(
            "Proposal contains duplicate players."
        )

    squad_by_id = {
        player["id"]: player
        for player
        in report["recommended"]["squad"]
    }

    expected_ids = set(
        squad_by_id
    )

    if set(all_ids) != expected_ids:
        raise ValueError(
            "Proposal does not match "
            "the recommended 15-player squad."
        )

    starters = [
        squad_by_id[player_id]
        for player_id
        in starter_ids
    ]

    bench = [
        squad_by_id[player_id]
        for player_id
        in bench_ids
    ]

    position_counts = {
        "GKP": 0,
        "DEF": 0,
        "MID": 0,
        "FWD": 0,
    }

    for player in starters:

        position_counts[
            player["position"]
        ] += 1

    if position_counts["GKP"] != 1:
        raise ValueError(
            "Starting XI must contain "
            "exactly one goalkeeper."
        )

    if not (
        3
        <= position_counts["DEF"]
        <= 5
    ):
        raise ValueError(
            "Starting XI must contain "
            "3-5 defenders."
        )

    if not (
        2
        <= position_counts["MID"]
        <= 5
    ):
        raise ValueError(
            "Starting XI must contain "
            "2-5 midfielders."
        )

    if not (
        1
        <= position_counts["FWD"]
        <= 3
    ):
        raise ValueError(
            "Starting XI must contain "
            "1-3 forwards."
        )

    bench_goalkeepers = [
        player
        for player in bench
        if player["position"] == "GKP"
    ]

    if len(bench_goalkeepers) != 1:
        raise ValueError(
            "Bench must contain "
            "exactly one goalkeeper."
        )

    if captain_id not in starter_ids:
        raise ValueError(
            "Captain must be in "
            "the starting XI."
        )

    if vice_id not in starter_ids:
        raise ValueError(
            "Vice-captain must be in "
            "the starting XI."
        )

    if captain_id == vice_id:
        raise ValueError(
            "Captain and vice-captain "
            "must be different players."
        )

    return (
        starters,
        bench,
        squad_by_id,
    )

@app.route(
    "/history",
)
def history():

    history_items = load_history()

    selected_gameweek = request.args.get(
        "gw",
        type=int,
    )

    available_gameweeks = [
        item["gameweek"]
        for item in history_items
    ]

    if (
        selected_gameweek
        not in available_gameweeks
    ):
        selected_gameweek = (
            available_gameweeks[0]
            if available_gameweeks
            else None
        )

    selected_item = next(
        (
            item
            for item in history_items
            if item["gameweek"]
            == selected_gameweek
        ),
        None,
    )

    selected_index = (
        available_gameweeks.index(
            selected_gameweek
        )
        if selected_gameweek
        in available_gameweeks
        else None
    )

    newer_gameweek = None
    older_gameweek = None

    if selected_index is not None:

        if selected_index > 0:
            newer_gameweek = (
                available_gameweeks[
                    selected_index - 1
                ]
            )

        if (
            selected_index
            < len(
                available_gameweeks
            ) - 1
        ):
            older_gameweek = (
                available_gameweeks[
                    selected_index + 1
                ]
            )

    return render_template(
        "history.html",
        history=history_items,
        selected_item=selected_item,
        selected_gameweek=
            selected_gameweek,
        available_gameweeks=
            available_gameweeks,
        newer_gameweek=
            newer_gameweek,
        older_gameweek=
            older_gameweek,
    )


@app.route(
    "/history/<int:gameweek>/collect",
    methods=["POST"],
)
def collect_history_results(
    gameweek,
):

    collect_gameweek_results(
        gameweek
    )

    return redirect(
        url_for("history")
    )


@app.route("/")
def index():

    report = load_weekly_report()

    if report is None:

        report = build_weekly_report()

        save_recommendation_snapshot(
            report
        )

        save_weekly_report(
            report
        )

    report["approval"] = (
        load_approval()
    )

    return render_template(
        "index.html",
        report=report,
    )

@app.route(
    "/refresh",
    methods=["POST"],
)
def refresh_analysis():

    clear_approval()

    old_report = (
        load_weekly_report()
    )

    constraints = (
        old_report.get(
            "constraints",
            {},
        )
        if old_report
        else {}
    )

    report = build_weekly_report(
        must_keep_ids=
            constraints.get(
                "must_keep_ids",
                [],
            ),
        must_include_ids=
            constraints.get(
                "must_include_ids",
                [],
            ),
    )

    save_recommendation_snapshot(
        report
    )

    save_weekly_report(
        report
    )

    return redirect(
        url_for("index")
    )

@app.route(
    "/keep-player",
    methods=["POST"],
)
def keep_player():

    report = load_weekly_report()

    if report is None:
        return (
            "No current weekly report.",
            409,
        )

    try:
        player_id = int(
            request.form[
                "player_id"
            ]
        )

    except (
        KeyError,
        ValueError,
    ):
        return (
            "Invalid player.",
            400,
        )

    current_ids = {
        player["id"]
        for player
        in (
            report[
                "current_starters"
            ]
            +
            report[
                "current_bench"
            ]
        )
    }

    if player_id not in current_ids:
        return (
            "KEEP can only be used "
            "for a player currently "
            "in your FPL squad.",
            400,
        )

    constraints = report.get(
        "constraints",
        {},
    )

    keep_ids = set(
        constraints.get(
            "must_keep_ids",
            [],
        )
    )

    include_ids = set(
        constraints.get(
            "must_include_ids",
            [],
        )
    )

    keep_ids.add(
        player_id
    )

    clear_approval()

    new_report = build_weekly_report(
        must_keep_ids=
            sorted(keep_ids),
        must_include_ids=
            sorted(include_ids),
    )

    save_recommendation_snapshot(
        new_report
    )

    save_weekly_report(
        new_report
    )

    return redirect(
        url_for("index")
    )

@app.route(
    "/remove-keep-player",
    methods=["POST"],
)
def remove_keep_player():

    report = load_weekly_report()

    if report is None:
        return (
            "No current weekly report.",
            409,
        )

    try:
        player_id = int(
            request.form[
                "player_id"
            ]
        )

    except (
        KeyError,
        ValueError,
    ):
        return (
            "Invalid player.",
            400,
        )

    constraints = report.get(
        "constraints",
        {},
    )

    keep_ids = set(
        constraints.get(
            "must_keep_ids",
            [],
        )
    )

    include_ids = set(
        constraints.get(
            "must_include_ids",
            [],
        )
    )

    keep_ids.discard(
        player_id
    )

    clear_approval()

    new_report = build_weekly_report(
        must_keep_ids=
            sorted(keep_ids),
        must_include_ids=
            sorted(include_ids),
    )

    save_recommendation_snapshot(
        new_report
    )

    save_weekly_report(
        new_report
    )

    return redirect(
        url_for("index")
    )

@app.route(
    "/clear-preferences",
    methods=["POST"],
)
def clear_preferences():

    report = load_weekly_report()

    if report is None:
        return (
            "No current weekly report.",
            409,
        )

    clear_approval()

    new_report = build_weekly_report(
        must_keep_ids=[],
        must_include_ids=[],
    )

    save_recommendation_snapshot(
        new_report
    )

    save_weekly_report(
        new_report
    )

    return redirect(
        url_for("index")
    )

@app.route(
    "/proposal",
    methods=["POST"],
)
def update_proposal():

    report = load_weekly_report()

    if report is None:
        return jsonify({
            "ok": False,
            "error":
                "No current weekly report exists.",
        }), 409

    deadline_info = (
        get_gameweek_deadline(
            report["gameweek"]
        )
    )

    if deadline_info["locked"]:
        return jsonify({
            "ok": False,
            "error":
                "The gameweek is locked.",
        }), 409

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    try:

        starter_ids = [
            int(player_id)
            for player_id
            in data["starters"]
        ]

        bench_ids = [
            int(player_id)
            for player_id
            in data["bench"]
        ]

        captain_id = int(
            data["captain_id"]
        )

        vice_id = int(
            data["vice_id"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return jsonify({
            "ok": False,
            "error":
                "Invalid proposal payload.",
        }), 400

    try:

        (
            starters,
            bench,
            squad_by_id,
        ) = validate_proposed_team(
            report,
            starter_ids,
            bench_ids,
            captain_id,
            vice_id,
        )

    except ValueError as exc:

        return jsonify({
            "ok": False,
            "error":
                str(exc),
        }), 400


    #
    # Reset selection flags across
    # the full proposed squad.
    #
    for player in (
        report["recommended"]["squad"]
    ):

        player["starter"] = (
            player["id"]
            in starter_ids
        )

        player["captain"] = (
            player["id"]
            == captain_id
        )


    report["starters"] = (
        starters
    )

    report["bench"] = (
        bench
    )

    report["captain"] = (
        squad_by_id[
            captain_id
        ]
    )

    report["vice"] = (
        squad_by_id[
            vice_id
        ]
    )

    report["recommended"][
        "vice_captain"
    ] = (
        squad_by_id[
            vice_id
        ]
    )


    #
    # Recalculate comparison against
    # the actual live FPL setup.
    #
    current_starter_ids = {
        player["id"]
        for player
        in report[
            "current_starters"
        ]
    }

    proposed_starter_ids = set(
        starter_ids
    )

    report["selection_changes"] = {

        "xi_out": [
            player
            for player
            in report[
                "current_starters"
            ]
            if player["id"]
            not in proposed_starter_ids
        ],

        "xi_in": [
            player
            for player
            in starters
            if player["id"]
            not in current_starter_ids
        ],

        "captain_changed":
            (
                report[
                    "current_captain"
                ]["id"]
                != captain_id
            ),

        "vice_changed":
            (
                report[
                    "current_vice"
                ]["id"]
                != vice_id
            ),
    }


    clear_approval()

    save_weekly_report(
        report
    )

    save_recommendation_snapshot(
        report
    )

    return jsonify({
        "ok": True,
    })

@app.route(
    "/approve",
    methods=["POST"],
)
def approve():

    snapshot = (
        load_recommendation_snapshot()
    )

    if snapshot is None:
        return (
            "No recommendation snapshot "
            "exists to approve.",
            409,
        )

    try:
        confirmed_hit_cost = int(
            request.form.get(
                "confirm_hit",
                0,
            )
        )
    except ValueError:
        confirmed_hit_cost = 0

    report = load_weekly_report()

    if (
        report is not None
        and
        report.get("gameweek")
        == snapshot.get("gameweek")
    ):
        archive_pre_deadline_plan(
            report,
            snapshot,
        )

    try:
        apply_approved_plan(
            snapshot,
            confirmed_hit_cost=
                confirmed_hit_cost,
        )

    except PlanApplyError as exc:
        return (
            f"FPL changes were not applied: {exc}",
            409,
        )

    #
    # The approved setup has now been applied
    # and verified against live FPL.
    #
    # Immediately build a fresh analysis from
    # the resulting live squad. This also means
    # the page returns to an unapproved state.
    #
    clear_approval()

    report = build_weekly_report()

    save_recommendation_snapshot(
        report
    )

    save_weekly_report(
        report
    )

    return redirect(
        url_for("index")
    )

@app.route(
    "/reject",
    methods=["POST"],
)
def reject():

    snapshot = (
        load_recommendation_snapshot()
    )

    if snapshot is None:
        return (
            "No recommendation snapshot "
            "exists to reject.",
            409,
        )

    save_approval({
        "rejected_at":
            datetime.now(
                UK_TIMEZONE
            ).isoformat(),

        "gameweek":
            snapshot["gameweek"],

        "status":
            "rejected",
    })

    return redirect(
        url_for("index")
    )

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )
