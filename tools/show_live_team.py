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
    get_access_token,
    get_my_team,
    get_bootstrap,
)


def main():

    access_token = get_access_token()

    team = get_my_team(
        access_token=access_token,
    )

    bootstrap = get_bootstrap()

    players = {
        p["id"]: p["web_name"]
        for p in bootstrap["elements"]
    }

    print()
    print("LIVE FPL SQUAD")
    print("==============")
    print()

    for pick in sorted(
        team["picks"],
        key=lambda p: p["position"],
    ):

        name = players.get(
            pick["element"],
            str(pick["element"]),
        )

        marker = ""

        if pick.get("is_captain"):
            marker = " (C)"
        elif pick.get("is_vice_captain"):
            marker = " (VC)"

        print(
            f"{pick['position']:>2}. "
            f"{name}{marker}"
        )

    print()
    print(
        "Bank: "
        f"£{team['transfers']['bank'] / 10:.1f}m"
    )


if __name__ == "__main__":
    main()
