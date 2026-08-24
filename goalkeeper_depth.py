import requests
from bs4 import BeautifulSoup


ROTOWIRE_URL = (
    "https://www.rotowire.com/"
    "soccer/premier-league-depth-charts-1/"
)


def get_goalkeeper_depth():

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

        #
        # Team name
        #
        team_name = None

        for child in team_block.find_all(
            recursive=False
        ):

            text = child.get_text(
                " ",
                strip=True
            )

            if (
                text
                and "Goalkeeper" not in text
            ):
                team_name = text
                break

        #
        # Fallback:
        # extract everything before the word
        # Goalkeeper from the whole block.
        #
        if not team_name:

            full_text = team_block.get_text(
                " ",
                strip=True
            )

            team_name = full_text.split(
                "Goalkeeper",
                1
            )[0].strip()

        #
        # Find player links inside only the
        # goalkeeper position block.
        #
        keepers = []

        for link in position_block.find_all(
            "a"
        ):

            name = link.get_text(
                " ",
                strip=True
            )

            if not name:
                continue

            #
            # RotoWire sometimes shows:
            #
            # David Raya
            # Kepa K. Arrizabalaga
            #
            # We'll clean names later when
            # matching to FPL.
            #
            if name not in keepers:
                keepers.append(name)

        if (
            team_name
            and keepers
        ):
            result[team_name] = keepers

    return result


if __name__ == "__main__":

    depth = get_goalkeeper_depth()

    print(
        f"Found {len(depth)} teams"
    )

    print()

    for team, keepers in depth.items():

        print(team)

        for number, keeper in enumerate(
            keepers,
            start=1
        ):

            print(
                f"  {number}. "
                f"{keeper}"
            )

        print()
