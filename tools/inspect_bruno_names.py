from fpl_api import get_bootstrap

from outfield_depth import (
    get_rotowire_outfield_depth,
    normalise_name,
)


print()
print("FPL")
print("=" * 80)

bootstrap = get_bootstrap()

teams = {
    team["id"]: team["name"]
    for team in bootstrap["teams"]
}

for player in bootstrap["elements"]:

    searchable = " ".join(
        [
            player.get("web_name", ""),
            player.get("first_name", ""),
            player.get("second_name", ""),
        ]
    ).lower()

    if "bruno" not in searchable:
        continue

    print()
    print(f"ID          : {player['id']}")
    print(f"Team        : {teams[player['team']]}")
    print(f"web_name    : {player['web_name']!r}")
    print(f"first_name  : {player.get('first_name', '')!r}")
    print(f"second_name : {player.get('second_name', '')!r}")

    full_name = (
        f"{player.get('first_name', '')} "
        f"{player.get('second_name', '')}"
    )

    print(
        f"normal web  : "
        f"{normalise_name(player['web_name'])!r}"
    )

    print(
        f"normal full : "
        f"{normalise_name(full_name)!r}"
    )


print()
print()
print("ROTOWIRE")
print("=" * 80)

rotowire = get_rotowire_outfield_depth()

for team, positions in rotowire.items():

    for position, players in positions.items():

        for player in players:

            name = player["name"]

            if "bruno" not in name.lower():
                continue

            print()
            print(f"Team        : {team}")
            print(f"Group       : {position}")
            print(f"Name        : {name!r}")
            print(
                f"Normal name : "
                f"{normalise_name(name)!r}"
            )
            print(
                f"Status      : "
                f"{player['status']!r}"
            )
            print(
                f"Order       : "
                f"{player['order']}"
            )