from pathlib import Path
import sys
import json


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from fpl_api import (
    get_access_token,
    get_my_team,
    get_planning_gameweek,
)

from optimizer import load_players

from transfer_optimizer import (
    optimise_transfers,
    MINIMUM_PAID_TRANSFER_GAIN,
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


def main():

    print()
    print("FPL TRANSFER PAYLOAD DRY RUN")
    print("============================")
    print()

    access_token = (
        get_access_token()
    )

    current_team = get_my_team(
        access_token=access_token,
    )

    planning_gameweek = (
        get_planning_gameweek()
    )

    players = load_players()

    results = []

    for transfer_count in range(
        0,
        4,
    ):

        result = optimise_transfers(
            players,
            current_team,
            planning_gameweek,
            transfer_count,
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

    if best_overall["hit_cost"] > 0:

        paid_gain = (
            best_overall["net_score"]
            - best_no_hit["net_score"]
        )

        if (
            paid_gain
            < MINIMUM_PAID_TRANSFER_GAIN
        ):
            recommended = best_no_hit

    if recommended["transfers"] == 0:

        print("Recommendation: HOLD")
        print()
        return

    pairs = pair_transfers(
        recommended
    )

    current_picks = {
        pick["element"]: pick
        for pick in current_team["picks"]
    }

    payload = {
        "confirmed": False,
        "entry": 5710014,
        "event": planning_gameweek,
        "transfers": [],
    }

    print(
        f"Planning Gameweek: "
        f"GW{planning_gameweek}"
    )

    print(
        f"Recommended transfers: "
        f"{recommended['transfers']}"
    )

    print(
        f"Hit cost: "
        f"{recommended['hit_cost']}"
    )

    print()

    for pair in pairs:

        outgoing = pair["out"]
        incoming = pair["in"]

        live_pick = current_picks[
            outgoing["id"]
        ]

        selling_price = (
            live_pick["selling_price"]
        )

        purchase_price = int(
            round(
                incoming["price"] * 10
            )
        )

        transfer = {
            "element_out":
                outgoing["id"],
            "element_in":
                incoming["id"],
            "purchase_price":
                purchase_price,
            "selling_price":
                selling_price,
        }

        payload[
            "transfers"
        ].append(
            transfer
        )

        print(
            f"{outgoing['name']}"
            f" -> "
            f"{incoming['name']}"
        )

        print(
            f"  Sell: "
            f"£{selling_price / 10:.1f}m"
        )

        print(
            f"  Buy:  "
            f"£{purchase_price / 10:.1f}m"
        )

        print()

    print("Payload:")
    print()

    print(
        json.dumps(
            payload,
            indent=2,
        )
    )

    print()
    print(
        "DRY RUN ONLY — "
        "nothing submitted to FPL."
    )


if __name__ == "__main__":
    main()
