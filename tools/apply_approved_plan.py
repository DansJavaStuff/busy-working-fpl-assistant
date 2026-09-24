from fpl_api import (
    ENTRY_ID,
    get_access_token,
    get_bootstrap,
    get_my_team,
    get_planning_gameweek,
    make_transfers,
    set_my_team,
    get_gameweek_deadline
)

class PlanApplyError(RuntimeError):
    """Expected apply failure with a message safe for the web UI."""

    def __init__(self, public_message):
        super().__init__(public_message)
        self.public_message = public_message


def build_picks(snapshot):

    starters = snapshot["starters"]
    bench = snapshot["bench"]

    captain_id = snapshot["captain_id"]
    vice_id = snapshot["vice_id"]

    if len(starters) != 11:
        raise PlanApplyError(
            f"Expected 11 starters, found {len(starters)}."
        )

    if len(bench) != 4:
        raise PlanApplyError(
            f"Expected 4 bench players, found {len(bench)}."
        )

    bench_gk = next(
        (
            p
            for p in bench
            if p["position"] == "GKP"
        ),
        None,
    )

    bench_outfield = [
        p
        for p in bench
        if p["position"] != "GKP"
    ]

    if bench_gk is None:
        raise PlanApplyError(
            "No goalkeeper found on bench."
        )

    if len(bench_outfield) != 3:
        raise PlanApplyError(
            "Expected exactly three outfield substitutes."
        )

    ordered = (
        starters
        + [bench_gk]
        + bench_outfield
    )

    ids = [
        p["id"]
        for p in ordered
    ]

    if len(ids) != len(set(ids)):
        raise PlanApplyError(
            "Duplicate player detected in proposed team."
        )

    starter_ids = {
        p["id"]
        for p in starters
    }

    if captain_id not in starter_ids:
        raise PlanApplyError(
            "Captain is not in starting XI."
        )

    if vice_id not in starter_ids:
        raise PlanApplyError(
            "Vice-captain is not in starting XI."
        )

    picks = []

    for position, player in enumerate(
        ordered,
        start=1,
    ):

        is_captain = (
            player["id"]
            == captain_id
        )

        is_vice = (
            player["id"]
            == vice_id
        )

        picks.append({
            "element":
                player["id"],
            "position":
                position,
            "multiplier":
                2
                if is_captain
                else (
                    1
                    if position <= 11
                    else 0
                ),
            "is_captain":
                is_captain,
            "is_vice_captain":
                is_vice,
        })

    return picks


def apply_approved_plan(
    snapshot,
    confirmed_hit_cost=0,
):

    planning_gameweek = (
        get_planning_gameweek()
    )

    deadline_info = (
        get_gameweek_deadline(
            planning_gameweek
        )
    )

    if deadline_info["locked"]:
        raise PlanApplyError(
            f"GW{planning_gameweek} is locked. "
            "No FPL changes can be submitted."
        )

    if (
        snapshot["gameweek"]
        != planning_gameweek
    ):
        raise PlanApplyError(
            f"Recommendation is for GW"
            f"{snapshot['gameweek']}, "
            f"but FPL is currently planning "
            f"GW{planning_gameweek}."
        )

    access_token = (
        get_access_token()
    )

    live_team = get_my_team(
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    live_ids = {
        pick["element"]
        for pick in live_team["picks"]
    }

    source_ids = set(
        snapshot["source_squad_ids"]
    )

    if live_ids != source_ids:
        raise PlanApplyError(
            "Live FPL squad has changed since "
            "this analysis was generated. "
            "Refresh analysis before approving."
        )

    approved_transfers = (
        snapshot["transfers"]
    )

    if approved_transfers:

        transfer_state = (
            live_team["transfers"]
        )

        free_transfers = max(
            0,
            transfer_state["limit"]
            - transfer_state["made"]
        )

        expected_hit_cost = (
            max(
                0,
                len(approved_transfers)
                - free_transfers,
            )
            * 4
        )

        if (
            expected_hit_cost
            != snapshot["hit_cost"]
        ):
            raise PlanApplyError(
                "The points cost has changed "
                "since this analysis was generated. "
                "Refresh analysis before approving."
            )

        if (
            expected_hit_cost > 0
            and
            confirmed_hit_cost
            != expected_hit_cost
        ):
            raise PlanApplyError(
                f"This plan costs "
                f"{expected_hit_cost} points. "
                "Explicit confirmation is required."
            )

        bootstrap = get_bootstrap()

        live_players = {
            p["id"]: p
            for p in bootstrap["elements"]
        }

        current_picks = {
            p["element"]: p
            for p in live_team["picks"]
        }

        transfers = []

        total_sell = 0
        total_buy = 0

        for transfer in approved_transfers:

            out_id = (
                transfer["element_out"]
            )

            in_id = (
                transfer["element_in"]
            )

            if out_id not in live_ids:
                raise PlanApplyError(
                    f"Outgoing player {out_id} "
                    "is no longer in the live squad."
                )

            if in_id in live_ids:
                raise PlanApplyError(
                    f"Incoming player {in_id} "
                    "is already in the live squad."
                )

            if in_id not in live_players:
                raise PlanApplyError(
                    f"Incoming player {in_id} "
                    "does not exist in current FPL data."
                )

            selling_price = (
                current_picks[out_id][
                    "selling_price"
                ]
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

        bank_after = (
            transfer_state["bank"]
            + total_sell
            - total_buy
        )

        if bank_after < 0:
            raise PlanApplyError(
                "Approved transfers are "
                "no longer affordable."
            )

        make_transfers(
            transfers=transfers,
            event=planning_gameweek,
            entry_id=ENTRY_ID,
            access_token=access_token,
        )

        live_team = get_my_team(
            entry_id=ENTRY_ID,
            access_token=access_token,
        )

    picks = build_picks(
        snapshot
    )

    proposed_ids = {
        p["element"]
        for p in picks
    }

    live_ids = {
        p["element"]
        for p in live_team["picks"]
    }

    if live_ids != proposed_ids:
        raise PlanApplyError(
            "Live squad after transfers does not "
            "match the proposed squad."
        )

    set_my_team(
        picks=picks,
        chip=None,
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    after = get_my_team(
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    expected_signature = [
        (
            p["element"],
            p["position"],
            p["multiplier"],
            p["is_captain"],
            p["is_vice_captain"],
        )
        for p in picks
    ]

    actual_signature = [
        (
            p["element"],
            p["position"],
            p["multiplier"],
            p["is_captain"],
            p["is_vice_captain"],
        )
        for p in sorted(
            after["picks"],
            key=lambda p:
                p["position"],
        )
    ]

    if (
        expected_signature
        != actual_signature
    ):
        raise PlanApplyError(
            "Live FPL team verification failed."
        )

    return after
