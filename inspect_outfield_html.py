import requests
from bs4 import BeautifulSoup

from outfield_depth import ROTOWIRE_URL


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

for team_block in soup.find_all(
    "div",
    class_="depth-charts__block"
):

    text = team_block.get_text(
        " ",
        strip=True
    )

    if not text.startswith("Liverpool"):
        continue

    print(
        team_block.prettify()
    )

    break