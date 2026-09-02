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


@app.route("/")
def index():

    report = build_weekly_report()

    return render_template(
        "index.html",
        report=report,
    )

@app.route(
    "/approve",
    methods=["POST"],
)
def approve():

    report = build_weekly_report()

    recommendation = (
        report["recommended"]
    )

    approval = {
        "gameweek":
            report["gameweek"],
        "status":
            "approved",
        "transfers":
            [],
        "model_score":
            recommendation[
                "net_score"
            ],
        "hit_cost":
            recommendation[
                "hit_cost"
            ],
    }

    for pair in (
        report[
            "recommended_pairs"
        ]
    ):

        approval[
            "transfers"
        ].append({
            "out_id":
                pair["out"]["id"],
            "out":
                pair["out"]["name"],
            "in_id":
                pair["in"]["id"],
            "in":
                pair["in"]["name"],
        })

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

    report = build_weekly_report()

    save_approval({
        "gameweek":
            report["gameweek"],
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
