import requests
import os
import requests
from dotenv import load_dotenv

BASE_URL = "https://fantasy.premierleague.com/api"
ENTRY_ID = 5710014

TOKEN_URL = (
    "https://account.premierleague.com/"
    "as/token"
)

CLIENT_ID = (
    "bfcbaf69-aade-4c1b-8f00-"
    "c1cb8a193030"
)

def get_bootstrap():
    response = requests.get(
        f"{BASE_URL}/bootstrap-static/",
        timeout=20
    )
    response.raise_for_status()
    return response.json()

def get_fixtures():
    response = requests.get(
        f"{BASE_URL}/fixtures/",
        timeout=20
    )
    response.raise_for_status()
    return response.json()

def get_players():
    data = get_bootstrap()

    teams = {
        team["id"]: team["name"]
        for team in data["teams"]
    }

    positions = {
        position["id"]: position["singular_name_short"]
        for position in data["element_types"]
    }

    players = []

    for player in data["elements"]:
        players.append({
            "id": player["id"],
            "name": player["web_name"],
            "team": teams[player["team"]],
            "position": positions[player["element_type"]],
            "price": player["now_cost"] / 10,
            "ownership": float(player["selected_by_percent"]),
            "status": player["status"],
        })

    return players

def get_entry(entry_id=ENTRY_ID):

    url = (
        "https://fantasy.premierleague.com/"
        f"api/entry/{entry_id}/"
    )

    response = requests.get(
        url,
        timeout=30
    )

    response.raise_for_status()

    return response.json()

def get_entry_picks(
    gameweek,
    entry_id=ENTRY_ID
):

    url = (
        "https://fantasy.premierleague.com/"
        f"api/entry/{entry_id}/"
        f"event/{gameweek}/picks/"
    )

    response = requests.get(
        url,
        timeout=30
    )

    response.raise_for_status()

    return response.json()

def get_gameweek_status():

    data = get_bootstrap()

    current = None
    next_gameweek = None

    for event in data["events"]:

        if event.get("is_current"):
            current = event["id"]

        if event.get("is_next"):
            next_gameweek = event["id"]

    return {
        "current": current,
        "next": next_gameweek,
    }

def get_planning_gameweek():

    status = get_gameweek_status()

    #
    # While a Gameweek is still being played,
    # we're normally planning for the next one.
    #
    if status["next"] is not None:
        return status["next"]

    #
    # Fallback if FPL isn't currently flagging
    # a next Gameweek.
    #
    if status["current"] is not None:
        return status["current"] + 1

    raise RuntimeError(
        "Unable to determine next FPL Gameweek"
    )

def get_latest_gameweek():

    data = get_bootstrap()

    current = next(
        (
            event["id"]
            for event in data["events"]
            if event.get("is_current")
        ),
        None
    )

    if current is not None:
        return current

    finished = [
        event["id"]
        for event in data["events"]
        if event.get("finished")
    ]

    if finished:
        return max(finished)

    return 1

def save_refresh_token(new_token):

    env_file = ".env"

    lines = []

    if os.path.exists(env_file):
        with open(
            env_file,
            "r",
            encoding="utf-8"
        ) as f:
            lines = f.readlines()

    updated = False

    for i, line in enumerate(lines):

        if line.startswith(
            "FPL_REFRESH_TOKEN="
        ):
            lines[i] = (
                f"FPL_REFRESH_TOKEN="
                f"{new_token}\n"
            )

            updated = True

    if not updated:
        lines.append(
            f"FPL_REFRESH_TOKEN="
            f"{new_token}\n"
        )

    with open(
        env_file,
        "w",
        encoding="utf-8"
    ) as f:
        f.writelines(lines)

    os.chmod(
        env_file,
        0o600
    )


def get_access_token():

    load_dotenv(
        override=True
    )

    refresh_token = os.getenv(
        "FPL_REFRESH_TOKEN"
    )

    if not refresh_token:
        raise RuntimeError(
            "FPL_REFRESH_TOKEN missing from .env"
        )

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type":
                "refresh_token",
            "refresh_token":
                refresh_token,
            "client_id":
                CLIENT_ID,
        },
        timeout=30,
    )
    
    if not response.ok:

        print(
            "FPL token refresh failed:",
            response.status_code
        )

        try:
            error_data = response.json()

            print(
                "Error:",
                error_data.get("error")
            )

            print(
                "Description:",
                error_data.get(
                    "error_description"
                )
            )

        except ValueError:

            print(
                "Response:",
                response.text[:500]
            )

        response.raise_for_status()

    data = response.json()

    access_token = data[
        "access_token"
    ]

    new_refresh_token = data.get(
        "refresh_token"
    )

    if (
        new_refresh_token
        and
        new_refresh_token
        != refresh_token
    ):

        save_refresh_token(
            new_refresh_token
        )

        print(
            "Refresh token rotated "
            "and saved safely."
        )

    return access_token

def get_my_team(
    entry_id=ENTRY_ID,
    access_token=None,
):

    if access_token is None:
        access_token = (
            get_access_token()
        )

    url = (
        "https://fantasy.premierleague.com/"
        f"api/my-team/{entry_id}/"
    )

    response = requests.get(
        url,
        headers={
            "X-API-Authorization":
                f"Bearer {access_token}",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()

def set_my_team(
    picks,
    chip=None,
    entry_id=ENTRY_ID,
    access_token=None,
):

    if access_token is None:
        access_token = (
            get_access_token()
        )

    url = (
        "https://fantasy.premierleague.com/"
        f"api/my-team/{entry_id}/"
    )

    response = requests.post(
        url,
        headers={
            "X-API-Authorization":
                f"Bearer {access_token}",
            "Content-Type":
                "application/json",
        },
        json={
            "chip": chip,
            "picks": picks,
        },
        timeout=30,
    )

    if not response.ok:

        print(
            "FPL team update failed:",
            response.status_code,
        )

        print(
            response.text[:1000]
        )

        response.raise_for_status()

    if response.content:
        return response.json()

    return None

if __name__ == "__main__":
    players = get_players()

    print(f"\nDownloaded {len(players)} FPL players\n")

    players.sort(key=lambda player: player["price"], reverse=True)

    print(
        f"{'Player':20} "
        f"{'Team':20} "
        f"{'Pos':5} "
        f"{'Price':>7} "
        f"{'Owned':>8}"
    )

    print("-" * 65)

    for player in players[:30]:
        print(
            f"{player['name']:20} "
            f"{player['team']:20} "
            f"{player['position']:5} "
            f"£{player['price']:5.1f} "
            f"{player['ownership']:7.1f}%"
        )
