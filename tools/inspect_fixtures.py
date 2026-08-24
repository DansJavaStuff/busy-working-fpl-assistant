from fpl_api import get_fixtures


fixtures = get_fixtures()

print(f"Downloaded {len(fixtures)} fixtures\n")

for fixture in fixtures[:10]:
    print(fixture)
