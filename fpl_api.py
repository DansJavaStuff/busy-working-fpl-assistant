import requests

BASE_URL = "https://fantasy.premierleague.com/api"


def get_bootstrap():
    response = requests.get(
        f"{BASE_URL}/bootstrap-static/",
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
