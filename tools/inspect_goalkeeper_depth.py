import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.rotowire.com/"
    "soccer/premier-league-depth-charts-1/"
)


def load_page():

    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0"
        },
    )

    response.raise_for_status()

    return response.text


def inspect_page():

    html = load_page()

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    print(
        "Downloaded",
        len(html),
        "characters"
    )

    #
    # First diagnostic:
    # find every occurrence of the text
    # "Goalkeeper" and inspect its parent.
    #
    goalkeeper_labels = soup.find_all(
        string=lambda text:
            text
            and text.strip() == "Goalkeeper"
    )

    print(
        "Goalkeeper sections found:",
        len(goalkeeper_labels)
    )

    print()

    for label in goalkeeper_labels[:5]:
        print("=" * 80)
        parent = label.parent
        print(
            "GOALKEEPER TAG:",
            parent.name
        )
        print(
            "GOALKEEPER CLASS:",
            parent.get("class")
        )
        print()
        current = parent
        for level in range(1, 6):
            current = current.parent
            if current is None:
                break

            print(
                f"PARENT {level}:",
                current.name,
                current.get("class")
            )

            print(
                current.get_text(
                    " ",
                    strip=True
                )[:300]
            )

            print()


if __name__ == "__main__":
    inspect_page()
