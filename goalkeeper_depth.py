import re
import unicodedata

import requests
from bs4 import BeautifulSoup

from fpl_api import get_bootstrap


ROTOWIRE_URL = (
    "https://www.rotowire.com/"
    "soccer/premier-league-depth-charts-1/"
)

NAME_ALIASES = {
    "alisson": "alisson becker",
}

GOALKEEPER_DEPTH_PROBABILITY = {
    1: 0.95,
    2: 0.05,
    3: 0.01,
    4: 0.01,
    5: 0.01,
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
    # Remove RotoWire middle initials:
    #
    # Martin M. Dubravka
    # Antonin A. Kinsky
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


def get_rotowire_goalkeeper_depth():

    response = requests.get(
        ROTOWIRE_URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0"
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    result = {}

    goalkeeper_labels = soup.find_all(
        string=lambda text:
            text
            and text.strip() == "Goalkeeper"
    )

    for label in goalkeeper_labels:

        position_block = label.find_parent(
            "div",
            class_="depth-charts__pos"
        )

        team_block = label.find_parent(
            "div",
            class_="depth-charts__block"
        )

        if (
            position_block is None
            or team_block is None
        ):
            continue

        full_text = team_block.get_text(
            " ",
            strip=True
        )

        team_name = full_text.split(
            "Goalkeeper",
            1
        )[0].strip()

        keepers = []

        for link in position_block.find_all(
            "a"
        ):

            name = link.get_text(
                " ",
                strip=True
            )

            if (
                name
                and name not in keepers
            ):
                keepers.append(name)

        if team_name and keepers:
            result[team_name] = keepers

    return result


def get_goalkeeper_depth():

    bootstrap = get_bootstrap()

    fpl_goalkeepers = [
        p
        for p in bootstrap["elements"]
        if p["element_type"] == 1
    ]

    rotowire_depth = (
        get_rotowire_goalkeeper_depth()
    )

    result = {}

    for rotowire_team, keepers in (
        rotowire_depth.items()
    ):

        for depth_number, rw_name in (
            enumerate(
                keepers,
                start=1
            )
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

            if len(candidates) != 1:
                continue

            player = candidates[0]

            result[player["id"]] = {
                "depth": depth_number,
                "expected_start_probability":
                    GOALKEEPER_DEPTH_PROBABILITY.get(
                        depth_number,
                        0.01
                    ),
                "rotowire_name": rw_name,
                "rotowire_team": rotowire_team,
                "fpl_name": player["web_name"],
            }

    return result


if __name__ == "__main__":

    depth = get_goalkeeper_depth()

    print(
        f"Matched {len(depth)} FPL goalkeepers"
    )

    print()

    for player_id, info in sorted(
        depth.items(),
        key=lambda item: (
            item[1]["rotowire_team"],
            item[1]["depth"],
        )
    ):

        print(
            f"{info['rotowire_team']:25} "
            f"{info['depth']}. "
            f"{info['fpl_name']:18} "
            f"Start "
            f"{info['expected_start_probability'] * 100:5.1f}% "
            f"(ID {player_id})"
        )
