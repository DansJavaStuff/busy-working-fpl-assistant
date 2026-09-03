from pathlib import Path
import json
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
    get_bootstrap,
    get_my_team,
    get_planning_gameweek,
    make_transfers,
)


APPROVAL_FILE = (
    PROJECT_ROOT
    / "data"
    / "weekly_approval.json"
)


def abort(message):
    print()
    print(f"ABORT: {message}")
    print("Nothing submitted to FPL.")
    return


def main():

    print()
    print("APPLY APPROVED FPL TRANSFERS")
    print("============================")
    print()

    if not APPROVAL_FILE.exists():
        return abort(
            "No approval file exists."
        )

    approval = json.loads(
        APPROVAL_FILE.read_text(
            encoding="utf-8"
        )
    )

    if approval.get("status") != "approved":
        return abort(
            "Current recommendation "
            "is not approved."
        )

    approved_transfers = (
        approval.get("transfers", [])
    )

    if not approved_transfers:
        return abort(
            "Approval contains no transfers."
        )

    if approval.get("hit_cost") != 0:
        return abort(
            "Approved plan includes "
            "a points hit."
        )

    planning_gameweek = (
        get_planning_gameweek()
    )

    if (
        approval.get("gameweek")
        != planning_gameweek
    ):
        return abort(
            "Approval is for "
            f"GW{approval.get('gameweek')}, "
            "but FPL is currently planning "
            f"GW{planning_gameweek}."
        )

    out_ids = [
        transfer["element_out"]
        for transfer
        in approved_transfers
    ]

    in_ids = [
        transfer["element_in"]
        for transfer
        in approved_transfers
    ]

    if len(out_ids) != len(set(out_ids)):
        return abort(
            "Duplicate outgoing player."
        )

    if len(in_ids) != len(set(in_ids)):
        return abort(
            "Duplicate incoming player."
        )

    access_token = (
        get_access_token()
    )

    current_team = get_my_team(
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    current_picks = {
        pick["element"]: pick
        for pick
        in current_team["picks"]
    }

    current_ids = set(
        current_picks
    )

    outs_present = [
        player_id in current_ids
        for player_id in out_ids
    ]

    ins_present = [
        player_id in current_ids
        for player_id in in_ids
    ]

    #
    # Idempotency:
    # if all outgoing players have gone
    # and all incoming players are present,
    # this exact plan has already happened.
    #
    if (
        not any(outs_present)
        and all(ins_present)
    ):
        print(
            "These approved transfers "
            "already appear to be applied."
        )
        print(
            "Nothing will be submitted again."
        )
        return

    #
    # Any half-applied / unexpected state
    # is unsafe.
    #
    if (
        not all(outs_present)
        or any(ins_present)
    ):
        return abort(
            "Live squad does not match "
            "the approved starting state."
        )

    transfer_state = (
        current_team["transfers"]
    )

    free_transfers = max(
        0,
        transfer_state["limit"]
        - transfer_state["made"]
    )

    transfer_count = len(
        approved_transfers
    )

    if transfer_count > free_transfers:
        return abort(
            f"Approved plan needs "
            f"{transfer_count} transfers, "
            f"but only {free_transfers} "
            "free transfers remain."
        )

    bootstrap = get_bootstrap()

    live_players = {
        player["id"]: player
        for player
        in bootstrap["elements"]
    }

    transfers = []

    total_sell = 0
    total_buy = 0

    print(
        f"Approved: GW"
        f"{planning_gameweek}"
    )
    print()

    for approved in approved_transfers:

        out_id = (
            approved["element_out"]
        )

        in_id = (
            approved["element_in"]
        )

        if in_id not in live_players:
            return abort(
                f"Incoming player ID "
                f"{in_id} no longer exists."
            )

        live_pick = (
            current_picks[out_id]
        )

        selling_price = (
            live_pick["selling_price"]
        )

        purchase_price = (
            live_players[in_id][
                "now_cost"
            ]
        )

        total_sell += selling_price
        total_buy += purchase_price

        transfers.append({
            "element_out":
                out_id,
            "element_in":
                in_id,
            "selling_price":
                selling_price,
            "purchase_price":
                purchase_price,
        })

        print(
            f"{approved['element_out_name']}"
            " -> "
            f"{approved['element_in_name']}"
        )

        print(
            f"  Sell £"
            f"{selling_price / 10:.1f}m"
            " / "
            f"Buy £"
            f"{purchase_price / 10:.1f}m"
        )

    bank = (
        transfer_state["bank"]
    )

    bank_after = (
        bank
        + total_sell
        - total_buy
    )

    print()
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
        f"Bank after:  "
        f"£{bank_after / 10:.1f}m"
    )
    print(
        f"Free transfers: "
        f"{free_transfers}"
    )
    print(
        "Points hit: 0"
    )

    if bank_after < 0:
        return abort(
            "Approved transfers are "
            "no longer affordable."
        )

    print()
    print(
        "This WILL make real changes "
        "to your FPL team."
    )
    print()

    expected = (
        f"APPLY APPROVED GW"
        f"{planning_gameweek}"
    )

    confirmation = input(
        f"Type exactly "
        f"'{expected}' to continue: "
    )

    if confirmation != expected:
        print()
        print(
            "ABORTED — nothing submitted."
        )
        return

    print()
    print(
        "Submitting approved "
        "transfers..."
    )

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
        "Reading live squad back..."
    )

    after = get_my_team(
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    after_ids = {
        pick["element"]
        for pick
        in after["picks"]
    }

    failed = False

    for approved in approved_transfers:

        out_id = (
            approved["element_out"]
        )

        in_id = (
            approved["element_in"]
        )

        if out_id in after_ids:
            print(
                "FAILED:",
                approved[
                    "element_out_name"
                ],
                "is still in squad.",
            )
            failed = True

        if in_id not in after_ids:
            print(
                "FAILED:",
                approved[
                    "element_in_name"
                ],
                "is missing from squad.",
            )
            failed = True

    if failed:
        raise RuntimeError(
            "Transfer verification failed."
        )

    after_transfers = (
        after["transfers"]
    )

    print()
    print(
        "SUCCESS: approved transfers "
        "are present in the live squad."
    )
    print()
    print(
        f"Live bank: "
        f"£{after_transfers['bank'] / 10:.1f}m"
    )


if __name__ == "__main__":
    main()
