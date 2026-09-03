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
    get_my_team,
    set_my_team,
)


REPORT_FILE = (
    PROJECT_ROOT
    / "data"
    / "weekly_report.json"
)


def abort(message):
    print()
    print(f"ABORT: {message}")
    print("Nothing submitted to FPL.")


def main():

    print()
    print("APPLY PROPOSED FPL TEAM")
    print("=======================")
    print()

    if not REPORT_FILE.exists():
        return abort(
            "weekly_report.json does not exist."
        )

    report = json.loads(
        REPORT_FILE.read_text(
            encoding="utf-8"
        )
    )

    starters = report["starters"]
    bench = report["bench"]

    captain = report["captain"]
    vice = report["vice"]

    if len(starters) != 11:
        return abort(
            f"Expected 11 starters, "
            f"found {len(starters)}."
        )

    if len(bench) != 4:
        return abort(
            f"Expected 4 bench players, "
            f"found {len(bench)}."
        )

    #
    # FPL positions:
    #
    # 1-11 = starting XI
    # 12   = substitute goalkeeper
    # 13-15 = outfield substitutes
    #
    bench_gk = next(
        (
            p for p in bench
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
        return abort(
            "No goalkeeper found on bench."
        )

    if len(bench_outfield) != 3:
        return abort(
            "Expected exactly three "
            "outfield substitutes."
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
        return abort(
            "Duplicate player detected."
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

    if set(ids) != live_ids:
        missing = live_ids - set(ids)
        extra = set(ids) - live_ids

        print(
            "Live squad does not match "
            "the proposed squad."
        )
        print(
            "Missing from proposal:",
            sorted(missing),
        )
        print(
            "Unexpected in proposal:",
            sorted(extra),
        )

        return abort(
            "Squad mismatch."
        )

    picks = []

    print("PROPOSED TEAM")
    print("-------------")
    print()

    for position, player in enumerate(
        ordered,
        start=1,
    ):

        is_captain = (
            player["id"]
            == captain["id"]
        )

        is_vice = (
            player["id"]
            == vice["id"]
        )

        multiplier = (
            2
            if is_captain
            else 1
        )

        marker = ""

        if is_captain:
            marker = " (C)"
        elif is_vice:
            marker = " (VC)"

        if position == 12:
            print()
            print("BENCH")
            print("-----")

        print(
            f"{position:>2}. "
            f"{player['name']}"
            f"{marker}"
        )

        picks.append({
            "element":
                player["id"],
            "position":
                position,
            "multiplier":
                multiplier
                if position <= 11
                else 0,
            "is_captain":
                is_captain,
            "is_vice_captain":
                is_vice,
        })

    #
    # Captain and vice must both be starters.
    #
    starter_ids = {
        p["id"]
        for p in starters
    }

    if captain["id"] not in starter_ids:
        return abort(
            "Captain is not in starting XI."
        )

    if vice["id"] not in starter_ids:
        return abort(
            "Vice-captain is not "
            "in starting XI."
        )

    print()
    print(
        "This WILL update your live "
        "FPL starting XI, bench order, "
        "captain and vice-captain."
    )
    print()

    expected = (
        f"APPLY GW"
        f"{report['gameweek']} TEAM"
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
    print("Submitting team selection...")

    set_my_team(
        picks=picks,
        chip=None,
        entry_id=ENTRY_ID,
        access_token=access_token,
    )

    print(
        "Team-selection request accepted."
    )

    print()
    print(
        "Reading live team back..."
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
        raise RuntimeError(
            "Team-selection verification "
            "failed."
        )

    print()
    print(
        "SUCCESS: live FPL team matches "
        "the proposed XI."
    )


if __name__ == "__main__":
    main()
