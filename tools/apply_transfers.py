from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from fpl_api import (
    ENTRY_ID,
    get_access_token,
    get_my_team,
    get_planning_gameweek,
    make_transfers,
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


def get_recommendation(
    players,
    current_team,
    planning_gameweek,
):

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

    best_overall = max(
        results,
        key=lambda r:
            r["net_score"],
    )

    best_no_hit = max(
        (
            r
            for r in results
            if r["hit_cost"] == 0
        ),
        key=lambda r:
            r["net_score"],
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

    return recommended


def main():

    print()
    print("LIVE FPL TRANSFER")
    print("=================")
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

    recommended = (
        get_recommendation(
            players,
            current_team,
            planning_gameweek,
        )
    )

    if recommended["transfers"] == 0:
        print("Recommendation is HOLD.")
        print("Nothing to submit.")
        return

    if recommended["hit_cost"] != 0:
        print(
            "ABORT: recommendation "
            "requires a points hit."
        )
        return

    pairs = pair_transfers(
        recommended
    )

    current_picks = {
        pick["element"]: pick
        for pick in current_team["picks"]
    }

    transfers = []

    total_sell = 0
    total_buy = 0

    bank = current_team["transfers"]["bank"]

    available_funds = (
        bank
        + total_sell
    )

    if total_buy > available_funds:

        print()
        print(
            "ABORT: transfers are "
            "no longer affordable."
        )

        print(
            f"Available: "
            f"£{available_funds / 10:.1f}m"
        )

        print(
            f"Required:  "
            f"£{total_buy / 10:.1f}m"
        )

        return

    bank_after = (
        bank
        + total_sell
        - total_buy
    )

    if bank_after < 0:

        print()
        print(
            "ABORT: combined transfers "
            "are no longer affordable."
        )

        print(
            f"Bank before: "
            f"£{bank / 10:.1f}m"
        )

        print(
            f"Total sales: "
            f"£{total_sell / 10:.1f}m"
        )

        print(
            f"Total buys:  "
            f"£{total_buy / 10:.1f}m"
        )

        print(
            f"Shortfall:   "
            f"£{-bank_after / 10:.1f}m"
        )

        return

    for pair in pairs:

        outgoing = pair["out"]
        incoming = pair["in"]

        if (
            outgoing["id"]
            not in current_picks
        ):
            print(
                "ABORT:",
                outgoing["name"],
                "is no longer in "
                "the live squad.",
            )
            return

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

        total_sell += selling_price
        total_buy += purchase_price

        transfers.append({
            "element_out":
                outgoing["id"],
            "element_in":
                incoming["id"],
            "purchase_price":
                purchase_price,
            "selling_price":
                selling_price,
        })

    print(
        f"Gameweek: GW"
        f"{planning_gameweek}"
    )
    print()

    for pair in pairs:
        print(
            f"{pair['out']['name']}"
            f" -> "
            f"{pair['in']['name']}"
        )

    print()
    print(
        f"Sell value: "
        f"£{total_sell / 10:.1f}m"
    )
    print(
        f"Buy cost:   "
        f"£{total_buy / 10:.1f}m"
    )
    print(
        f"Bank before: "
        f"£{bank / 10:.1f}m"
    )

    print(
        f"Bank after:  "
        f"£{bank_after / 10:.1f}m"
    )
    print(
        f"Hit:        "
        f"{recommended['hit_cost']}"
    )
    print()

    confirmation = input(
        f"Type exactly "
        f"'APPLY GW{planning_gameweek} TRANSFERS' "
        f"to continue: "
    )

    expected = (
        f"APPLY GW"
        f"{planning_gameweek} "
        f"TRANSFERS"
    )

    if confirmation != expected:
        print()
        print("ABORTED — nothing submitted.")
        return

    print()
    print("Submitting transfers...")

    make_transfers(
        transfers=transfers,
        event=planning_gameweek,
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    print(
        "Transfer request accepted."
    )

    print()
    print(
        "Reading team back "
        "for verification..."
    )

    after = get_my_team(
        access_token=access_token,
    )

    after_ids = {
        pick["element"]
        for pick in after["picks"]
    }

    failed = False

    for pair in pairs:

        outgoing = pair["out"]
        incoming = pair["in"]

        if outgoing["id"] in after_ids:
            print(
                "FAILED:",
                outgoing["name"],
                "is still in squad.",
            )
            failed = True

        if incoming["id"] not in after_ids:
            print(
                "FAILED:",
                incoming["name"],
                "is missing from squad.",
            )
            failed = True

    if failed:
        raise RuntimeError(
            "Transfer verification failed."
        )

    print()
    print(
        "SUCCESS: transfers verified."
    )


if __name__ == "__main__":
    main()
