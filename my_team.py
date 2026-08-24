from fpl_api import (
    get_bootstrap,
    get_entry,
    get_entry_picks,
    get_latest_gameweek,
)

ENTRY_ID = 5710014


def get_current_squad(gameweek=None):

    if gameweek is None:
        gameweek = get_latest_gameweek()

    bootstrap = get_bootstrap()
    entry = get_entry(ENTRY_ID)
    picks_data = get_entry_picks(
        gameweek,
        ENTRY_ID
    )

    players_by_id = {
        p["id"]: p
        for p in bootstrap["elements"]
    }

    teams_by_id = {
        t["id"]: t["name"]
        for t in bootstrap["teams"]
    }

    squad = []

    for pick in picks_data["picks"]:

        player = players_by_id[
            pick["element"]
        ]

        squad.append({
            "id": player["id"],
            "name": player["web_name"],
            "team_id": player["team"],
            "team": teams_by_id[
                player["team"]
            ],
            "position_id": player[
                "element_type"
            ],
            "price": player["now_cost"],
            "current_price": (
                player["now_cost"]
            ),
            "squad_position": pick[
                "position"
            ],
            "captain": pick[
                "is_captain"
            ],
            "vice_captain": pick[
                "is_vice_captain"
            ],
        })

    return {
        "entry_id": ENTRY_ID,
        "gameweek": gameweek,
        "team_name": entry["name"],
        "team_name": entry["name"],
        "bank": picks_data[
            "entry_history"
        ]["bank"],
        "squad_value": picks_data[
            "entry_history"
        ]["value"],
        "squad": squad,
    }

if __name__ == "__main__":

    team = get_current_squad()

    print()
    print(team["team_name"])
    print(
        f"Bank: £{team['bank'] / 10:.1f}m"
    )

    for p in team["squad"]:
        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"£{p['price'] / 10:.1f}m"
        )

