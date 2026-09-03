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
    set_my_team,
)


def main():
    access_token = (
        get_access_token()
    )

    current = get_my_team(
        access_token=access_token,
    )

    print()
    print("FPL TEAM WRITE TEST")
    print("===================")
    print()

    picks = []

    for pick in current["picks"]:

        picks.append({
            "element":
                pick["element"],
            "position":
                pick["position"],
            "is_captain":
                pick["is_captain"],
            "is_vice_captain":
                pick[
                    "is_vice_captain"
                ],
        })

    print(
        "Submitting current team "
        "unchanged..."
    )

    result = set_my_team(
        picks=picks,
        chip=None,
        access_token=access_token,
    )

    print()
    print("Write accepted.")
    print()

    if result:

        print(
            "Returned picks:",
            len(
                result.get(
                    "picks",
                    []
                )
            ),
        )

    print()
    print(
        "Reading team back "
        "for verification..."
    )

    after = get_my_team(
        access_token=access_token,
    )

    before_signature = [
        (
            p["element"],
            p["position"],
            p["is_captain"],
            p["is_vice_captain"],
        )
        for p in current["picks"]
    ]

    after_signature = [
        (
            p["element"],
            p["position"],
            p["is_captain"],
            p["is_vice_captain"],
        )
        for p in after["picks"]
    ]

    if (
        before_signature
        == after_signature
    ):

        print()
        print(
            "SUCCESS: team unchanged "
            "after write."
        )

    else:

        print()
        print(
            "WARNING: team changed."
        )

        raise RuntimeError(
            "Verification failed"
        )


if __name__ == "__main__":
    main()
