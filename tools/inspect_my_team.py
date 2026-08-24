from fpl_api import (
    get_bootstrap,
    get_entry,
    get_entry_picks,
    get_latest_gameweek,
    get_planning_gameweek,
)

GAMEWEEK  = get_latest_gameweek()
PLANNING_GAMEWEEK = get_planning_gameweek()

print(
    f"Latest squad: GW{GAMEWEEK}"
)
print(
    f"Planning for: GW{PLANNING_GAMEWEEK}"
)

bootstrap = get_bootstrap()
entry = get_entry()
picks_data = get_entry_picks(
    GAMEWEEK
)

players = {
    p["id"]: p
    for p in bootstrap["elements"]
}

teams = {
    t["id"]: t["name"]
    for t in bootstrap["teams"]
}


print()
print("MY FPL ENTRY")
print("=" * 70)

print(
    f"Team: {entry.get('name')}"
)

print(
    f"Manager: "
    f"{entry.get('player_first_name')} "
    f"{entry.get('player_last_name')}"
)

print()
print(
    f"GW{GAMEWEEK} PICKS"
)
print("=" * 70)

for pick in picks_data["picks"]:

    p = players[
        pick["element"]
    ]

    team = teams[
        p["team"]
    ]

    marker = ""

    if pick["is_captain"]:
        marker = " (C)"

    elif pick["is_vice_captain"]:
        marker = " (VC)"

    print(
        f"{pick['position']:2}. "
        f"{p['web_name']:18} "
        f"{team:18} "
        f"£{p['now_cost'] / 10:4.1f}m"
        f"{marker}"
    )


print()
print("ENTRY HISTORY")
print("=" * 70)

history = picks_data.get(
    "entry_history",
    {}
)

for key, value in history.items():
    print(
        f"{key:25} {value}"
    )
