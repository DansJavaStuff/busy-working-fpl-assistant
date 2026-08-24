from fpl_api import get_my_team


data = get_my_team()

print()
print("TRANSFERS")
print(data["transfers"])

print()
print("CHIPS")

for chip in data["chips"]:
    print(chip)

print()
print("CURRENT PICKS")

for pick in data["picks"]:
    print(
        "element:",
        pick["element"],
        "selling_price:",
        pick["selling_price"],
    )
