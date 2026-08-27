import re
import unicodedata

import requests
from bs4 import BeautifulSoup

from fpl_api import get_bootstrap


ROTOWIRE_URL = (
    "https://www.rotowire.com/"
    "soccer/premier-league-depth-charts-1/"
)

POSITION_MAP = {
    "Defender": "DEF",
    "Midfielder": "MID",
    "Forward": "FWD",
}

TEAM_ALIASES = {
    "afc bournemouth": "bournemouth",
    "brighton hove albion": "brighton",
    "leeds united": "leeds",
    "manchester city": "man city",
    "manchester united": "man utd",
    "newcastle united": "newcastle",
    "nottingham forest": "nott m forest",
    "tottenham hotspur": "spurs",
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

    # Remove RotoWire middle initials.
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

def normalise_team_name(name):

    normalised = normalise_name(name)

    return TEAM_ALIASES.get(
        normalised,
        normalised,
    )

def get_rotowire_outfield_depth():

    response = requests.get(
        ROTOWIRE_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    result = {}

    for position_label, fpl_position in (
        POSITION_MAP.items()
    ):

        labels = soup.find_all(
            string=lambda text:
                text
                and text.strip()
                == position_label
        )

        for label in labels:

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

            #
            # The team name is held at the start
            # of the complete team block.
            #
            full_text = team_block.get_text(
                " ",
                strip=True
            )

            first_position = None

            for possible_label in (
                "Goalkeeper",
                "Defender",
                "Midfielder",
                "Forward",
            ):

                index = full_text.find(
                    possible_label
                )

                if (
                    index >= 0
                    and (
                        first_position is None
                        or index < first_position
                    )
                ):
                    first_position = index

            if first_position is None:
                continue

            team_name = full_text[
                :first_position
            ].strip()

            players = []

            for order_number, link in enumerate(
                position_block.find_all("a"),
                start=1,
            ):

                name = link.get_text(
                    " ",
                    strip=True
                )

                if not name:
                    continue

                player_item = link.find_parent(
                    "li"
                )

                status = None

                if player_item is not None:

                    injury = player_item.find(
                        "span",
                        class_="depth-charts__inj",
                    )

                    if injury is not None:
                        status = injury.get_text(
                            " ",
                            strip=True,
                        )

                players.append(
                    {
                        "name": name,
                        "order": order_number,
                        "status": status,
                    }
                )

            if not team_name:
                continue

            result.setdefault(
                team_name,
                {}
            )

            result[team_name][
                fpl_position
            ] = players

    return result


def get_outfield_depth():

    bootstrap = get_bootstrap()
    
    fpl_teams = {
        team["id"]: team["name"]
        for team in bootstrap["teams"]
    }

    element_positions = {
        position["id"]:
            position["singular_name_short"]
        for position
        in bootstrap["element_types"]
    }

    fpl_players = [
        p
        for p in bootstrap["elements"]
        if element_positions[
            p["element_type"]
        ] != "GKP"
    ]

    rotowire_depth = (
        get_rotowire_outfield_depth()
    )

    result = {}
    unmatched = []

    for rotowire_team, positions in (
        rotowire_depth.items()
    ):

        for position, players in (
            positions.items()
        ):

            for rw_player in players:

                rw_name = rw_player["name"]
                rotowire_order = rw_player["order"]
                rotowire_status = rw_player["status"]

                rw_normal = normalise_name(
                    rw_name
                )

                candidates = []

                for p in fpl_players:

                    fpl_team = fpl_teams[
                        p["team"]
                    ]

                    if (
                        normalise_team_name(fpl_team)
                        != normalise_team_name(rotowire_team)
                    ):
                        continue

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
                        rotowire_team == "Arsenal"
                        and "bruno" in rw_normal
                    ):

                        print()
                        print("BRUNO MATCH DEBUG")
                        print(f"rw_name       = {rw_name!r}")
                        print(f"rw_normal     = {rw_normal!r}")
                        print(f"fpl web_name  = {p['web_name']!r}")
                        print(f"fpl_name      = {fpl_name!r}")
                        print(f"full_name     = {full_name!r}")
                        print(
                            "exact web     =",
                            fpl_name == rw_normal
                        )
                        print(
                            "exact full    =",
                            full_name == rw_normal
                        )
                        print(
                            "prefix full   =",
                            full_name.startswith(
                                f"{rw_normal} "
                            )
                        )
                        print(
                            "suffix web    =",
                            rw_normal.endswith(
                                f" {fpl_name}"
                            )
                        )

                    if (
                        fpl_name == rw_normal
                        or full_name == rw_normal
                        or full_name.startswith(
                            f"{rw_normal} "
                        )
                        or rw_normal.endswith(
                            f" {fpl_name}"
                        )
                    ):
                        candidates.append(p)

                if len(candidates) != 1:

                    unmatched.append(
                        {
                            "team":
                                rotowire_team,
                            "position":
                                position,
                            "rotowire_order":
                                rotowire_order,
                            "rotowire_status":
                                rotowire_status,
                            "rotowire_name":
                                rw_name,
                            "matches":
                                len(candidates),
                        }
                    )

                    continue

                player = candidates[0]

                result[player["id"]] = {
                    "rotowire_order":
                        rotowire_order,
                    "rotowire_status":
                        rotowire_status,
                    "rotowire_name":
                        rw_name,
                    "rotowire_team":
                        rotowire_team,
                    "fpl_name":
                        player["web_name"],
                    "position":
                        position,
                }

    return result, unmatched


if __name__ == "__main__":

    depth, unmatched = (
        get_outfield_depth()
    )

    print(
        f"Matched {len(depth)} "
        f"FPL outfield players"
    )

    print(
        f"Unmatched {len(unmatched)} "
        f"RotoWire players"
    )

    print()

    for player_id, info in sorted(
        depth.items(),
        key=lambda item: (
            item[1]["rotowire_team"],
            item[1]["position"],
            item[1]["rotowire_order"],
        )
    ):

        status = (
            info["rotowire_status"]
            or "-"
        )

        print(
            f"{info['rotowire_team']:25} "
            f"{info['position']:3} "
            f"{info['rotowire_order']:2}. "
            f"{info['fpl_name']:18} "
            f"{status:4} "
            f"(ID {player_id})"
        )

    print()
    print("UNMATCHED")
    print("-" * 72)

    for info in unmatched:

        status = (
            info["rotowire_status"]
            or "-"
        )

        print(
            f"{info['team']:25} "
            f"{info['position']:3} "
            f"{info['rotowire_order']:2}. "
            f"{info['rotowire_name']:25} "
            f"{status:4} "
            f"matches={info['matches']}"
        )