"""Public FPL gameweek and league report.

Uses only public Fantasy Premier League API endpoints.
It does NOT call get_my_team(), get_access_token(), or read/rotate
FPL_REFRESH_TOKEN.
"""

import math
import requests

from fpl_api import BASE_URL, ENTRY_ID, get_bootstrap, get_entry

TIMEOUT = 30


def get_entry_history(entry_id=ENTRY_ID):
    response = requests.get(
        f"{BASE_URL}/entry/{entry_id}/history/",
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def get_league_standings(league_id, page=1):
    response = requests.get(
        f"{BASE_URL}/leagues-classic/{league_id}/standings/",
        params={"page_standings": page},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def latest_finished_gameweek():
    bootstrap = get_bootstrap()
    finished = [
        event["id"]
        for event in bootstrap["events"]
        if event.get("finished")
    ]
    return max(finished) if finished else None


def find_entry_on_league_page(league_id, entry_id, entry_rank):
    page = max(1, math.ceil(entry_rank / 50))
    data = get_league_standings(league_id, page)

    for row in data.get("standings", {}).get("results", []):
        if row.get("entry") == entry_id:
            return row

    return None


def movement(current_rank, previous_rank):
    if not current_rank or not previous_rank:
        return "-"

    change = previous_rank - current_rank

    if change > 0:
        return f"↑ {change}"
    if change < 0:
        return f"↓ {abs(change)}"
    return "→"


def league_type_name(value):
    return {
        "x": "Private",
        "s": "System",
    }.get(value, value or "Unknown")


def print_header(entry, latest):
    player_name = " ".join(
        part
        for part in [
            entry.get("player_first_name"),
            entry.get("player_last_name"),
        ]
        if part
    )

    team_name = entry.get("name", "FPL Team")

    print()
    print(team_name.upper())
    print("=" * max(24, len(team_name)))

    if player_name:
        print(f"Manager:          {player_name}")

    print(f"Entry ID:         {entry.get('id', ENTRY_ID)}")

    if latest:
        print(f"Latest Gameweek:  GW{latest['event']}")
        print(f"Gameweek points:  {latest['points']}")
        print(f"Gameweek rank:    {latest['rank']:,}")
        print(f"Total points:     {latest['total_points']}")
        print(f"Overall rank:     {latest['overall_rank']:,}")

        previous_overall = latest.get("previous_overall_rank")
        if previous_overall:
            print(
                f"Overall movement: "
                f"{previous_overall:,} -> {latest['overall_rank']:,} "
                f"{movement(latest['overall_rank'], previous_overall)}"
            )
    else:
        print(f"Total points:     {entry.get('summary_overall_points', 0)}")
        overall_rank = entry.get("summary_overall_rank")
        if overall_rank:
            print(f"Overall rank:     {overall_rank:,}")


def print_leagues(entry):
    classic = entry.get("leagues", {}).get("classic", [])

    if not classic:
        print("\nNo classic leagues found.")
        return

    private = [
        league for league in classic
        if league.get("league_type") == "x"
    ]
    system = [
        league for league in classic
        if league.get("league_type") != "x"
    ]

    for title, leagues in [
        ("MINI-LEAGUES", private),
        ("OTHER / SYSTEM LEAGUES", system),
    ]:
        if not leagues:
            continue

        print()
        print(title)
        print("-" * 78)
        print(
            f"{'League':34} "
            f"{'Rank':>8} "
            f"{'Previous':>10} "
            f"{'Move':>8} "
            f"{'Type':>10}"
        )
        print("-" * 78)

        for league in sorted(
            leagues,
            key=lambda item: (
                item.get("entry_rank") is None,
                item.get("entry_rank") or 999999999,
            ),
        ):
            rank = league.get("entry_rank")
            last_rank = league.get("entry_last_rank")
            move = movement(rank, last_rank)

            if rank:
                try:
                    row = find_entry_on_league_page(
                        league["id"],
                        ENTRY_ID,
                        rank,
                    )
                    if row:
                        rank = row.get("rank", rank)
                        last_rank = row.get("last_rank", last_rank)
                        move = movement(rank, last_rank)
                except requests.RequestException:
                    pass

            rank_text = f"{rank:,}" if rank else "-"
            last_text = f"{last_rank:,}" if last_rank else "-"

            print(
                f"{league.get('name', 'Unknown')[:34]:34} "
                f"{rank_text:>8} "
                f"{last_text:>10} "
                f"{move:>8} "
                f"{league_type_name(league.get('league_type')):>10}"
            )


def main():
    entry = get_entry()
    history = get_entry_history()
    current = history.get("current", [])
    latest_finished = latest_finished_gameweek()

    latest = None

    if current:
        if latest_finished is not None:
            latest = next(
                (
                    row for row in current
                    if row.get("event") == latest_finished
                ),
                None,
            )

        if latest is None:
            latest = max(
                current,
                key=lambda row: row.get("event", 0),
            )

    print_header(entry, latest)
    print_leagues(entry)

    print()
    print(
        "Public API only: this report does not use or rotate "
        "FPL_REFRESH_TOKEN."
    )
    print()


if __name__ == "__main__":
    main()
