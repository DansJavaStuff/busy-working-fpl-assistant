from flask import Flask, render_template

from fpl_api import (
    get_my_team,
    get_planning_gameweek,
)

from optimizer import load_players

from transfer_optimizer import (
    optimise_transfers,
    MINIMUM_FREE_TRANSFER_GAIN,
    MINIMUM_PAID_TRANSFER_GAIN,
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


def build_weekly_report():

    planning_gameweek = (
        get_planning_gameweek()
    )

    current_team = get_my_team()

    players = load_players()

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

    approval = load_approval()

    return {
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
        "starters":
            starters,
        "bench":
            bench,
        "captain":
            captain,
        "vice":
            recommended["vice_captain"],
        "approval":
            approval,
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

    return json.loads(
        REPORT_FILE.read_text(
            encoding="utf-8"
        )
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

    approval = {
        "approved_at":
            datetime.now(
                UK_TIMEZONE
            ).isoformat(),

        "gameweek":
            snapshot["gameweek"],

        "status":
            "approved",

        "model_score":
            snapshot["model_score"],

        "hit_cost":
            snapshot["hit_cost"],

        "transfers":
            snapshot["transfers"],
    }

    save_approval(
        approval
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
        debug=True,
    )
