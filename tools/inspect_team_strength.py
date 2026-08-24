from fpl_api import get_bootstrap


data = get_bootstrap()

teams = data["teams"]

print(
    f"{'Team':20} "
    f"{'Home':>6} "
    f"{'Away':>6} "
    f"{'Atk H':>6} "
    f"{'Atk A':>6} "
    f"{'Def H':>6} "
    f"{'Def A':>6}"
)

print("-" * 68)

for team in teams:

    print(
        f"{team['name']:20} "
        f"{str(team['strength_overall_home']):>6} "
        f"{str(team['strength_overall_away']):>6} "
        f"{str(team['strength_attack_home']):>6} "
        f"{str(team['strength_attack_away']):>6} "
        f"{str(team['strength_defence_home']):>6} "
        f"{str(team['strength_defence_away']):>6}"
    )
