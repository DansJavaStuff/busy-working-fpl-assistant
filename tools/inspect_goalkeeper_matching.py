import re
import unicodedata

from fpl_api import get_bootstrap
from goalkeeper_depth import get_goalkeeper_depth

NAME_ALIASES = {
    "alisson": "alisson becker",
}

def normalise_name(name):

    name = unicodedata.normalize(
        "NFKD",
        name
    )

    name = "".join(
        c
        for c in name
        if not unicodedata.combining(c)
    )

    #
    # Remove RotoWire middle initials such as:
    #
    # Martin M. Dubravka
    # David Raya
    #
    name = re.sub(
        r"\b[A-Z]\.\s*",
        "",
        name
    )

    name = name.lower()

    name = re.sub(
        r"[^a-z0-9]+",
        " ",
        name
    )

    return " ".join(
        name.split()
    )

def main():

    bootstrap = get_bootstrap()

    fpl_goalkeepers = [
        p
        for p in bootstrap["elements"]
        if p["element_type"] == 1
    ]

    teams = {
        t["id"]: t["name"]
        for t in bootstrap["teams"]
    }

    depth = get_goalkeeper_depth()

    print()
    print("GOALKEEPER DEPTH MATCHING")
    print("=" * 90)

    matched = 0
    unmatched = []

    for rotowire_team, keepers in depth.items():

        print()
        print(rotowire_team)
        print("-" * 90)

        for depth_number, rw_name in enumerate(
            keepers,
            start=1
        ):

            rw_normal = normalise_name(
                rw_name
            )

            rw_normal = NAME_ALIASES.get(
                rw_normal,
                rw_normal
            )

            candidates = []

            for p in fpl_goalkeepers:

                fpl_name = normalise_name(
                    p["web_name"]
                )

                full_name = normalise_name(
                    (
                        f"{p.get('first_name', '')} "
                        f"{p.get('second_name', '')}"
                    )
                )

                #
                # Match either:
                #
                # Raya == David Raya
                # Dubravka == Martin Dubravka
                #
                if (
                    fpl_name == rw_normal
                    or
                    full_name == rw_normal
                    or
                    rw_normal.endswith(
                        f" {fpl_name}"
                    )
                ):
                    candidates.append(p)

            if len(candidates) == 1:

                p = candidates[0]

                print(
                    f"{depth_number}. "
                    f"{rw_name:30} "
                    f"-> "
                    f"{p['web_name']:18} "
                    f"{teams[p['team']]}"
                )

                matched += 1

            else:

                print(
                    f"{depth_number}. "
                    f"{rw_name:30} "
                    f"-> NO UNIQUE MATCH "
                    f"({len(candidates)} candidates)"
                )

                unmatched.append(
                    (
                        rotowire_team,
                        depth_number,
                        rw_name,
                    )
                )

    print()
    print("=" * 90)
    print(
        f"Matched:   {matched}"
    )
    print(
        f"Unmatched: {len(unmatched)}"
    )

    if unmatched:

        print()
        print("UNMATCHED KEEPERS")
        print("-" * 90)

        for (
            team,
            depth_number,
            name,
        ) in unmatched:

            print(
                f"{team:25} "
                f"{depth_number}. "
                f"{name}"
            )


if __name__ == "__main__":
    main()
