"""FPL gameweek and league performance report.

Uses public Fantasy Premier League endpoints and is safe to run independently
of the optimiser. It can later become the data layer for a web dashboard.
"""

import math
import requests

from fpl_api import BASE_URL, ENTRY_ID, get_bootstrap, get_entry

TIMEOUT = 30
PAGE_SIZE = 50
MAX_PRIVATE_LEAGUE_PAGES = 100


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


def get_latest_finished_event():
    finished = [
        event
        for event in get_bootstrap()["events"]
        if event.get("finished")
    ]
    return max(finished, key=lambda event: event["id"]) if finished else None


def movement(current_rank, previous_rank):
    if not current_rank or not previous_rank:
        return "-"
    change = previous_rank - current_rank
    if change > 0:
        return f"↑ {change:,}"
    if change < 0:
        return f"↓ {abs(change):,}"
    return "→"


def signed(value):
    if value is None:
        return "-"
    return f"+{value}" if value > 0 else str(value)


def find_entry_on_league_page(league_id, entry_id, entry_rank):
    page = max(1, math.ceil(entry_rank / PAGE_SIZE))
    data = get_league_standings(league_id, page)

    for row in data.get("standings", {}).get("results", []):
        if row.get("entry") == entry_id:
            return row

    return None


def get_private_league_size(league_id):
    total = 0

    for page in range(1, MAX_PRIVATE_LEAGUE_PAGES + 1):
        data = get_league_standings(league_id, page)
        standings = data.get("standings", {})
        rows = standings.get("results", [])

        total += len(rows)

        if not standings.get("has_next") or not rows:
            return total

    return None


def print_summary(entry, latest, previous, event_info):
    team_name = entry.get("name", "FPL Team")
    manager = " ".join(
        p for p in [
            entry.get("player_first_name"),
            entry.get("player_last_name"),
        ] if p
    )

    print()
    print(team_name.upper())
    print("=" * max(24, len(team_name)))

    if manager:
        print(f"Manager:             {manager}")

    print(f"Entry ID:            {entry.get('id', ENTRY_ID)}")

    if not latest:
        return

    print(f"Latest Gameweek:     GW{latest['event']}")
    print(f"Gameweek points:     {latest['points']}")

    average = event_info.get("average_entry_score") if event_info else None
    highest = event_info.get("highest_score") if event_info else None

    if average is not None:
        print(f"GW average:          {average}")
        print(f"Vs GW average:       {signed(latest['points'] - average)}")

    if highest is not None:
        print(f"GW highest score:    {highest}")

    print(f"Gameweek rank:       {latest['rank']:,}")
    print(f"Total points:        {latest['total_points']}")
    print(f"Overall rank:        {latest['overall_rank']:,}")

    previous_overall = latest.get("previous_overall_rank")
    if previous_overall:
        print(
            f"Overall movement:    "
            f"{previous_overall:,} -> {latest['overall_rank']:,} "
            f"{movement(latest['overall_rank'], previous_overall)}"
        )

    if previous:
        print()
        print("GAMEWEEK COMPARISON")
        print("-" * 40)
        print(f"GW{previous['event']}:             {previous['points']} points")
        print(f"GW{latest['event']}:             {latest['points']} points")
        print(
            f"Difference:          "
            f"{signed(latest['points'] - previous['points'])} points"
        )


def print_leagues(entry):
    leagues = entry.get("leagues", {}).get("classic", [])
    private = [l for l in leagues if l.get("league_type") == "x"]
    system = [l for l in leagues if l.get("league_type") != "x"]

    for heading, group in [
        ("MINI-LEAGUES", private),
        ("OTHER / SYSTEM LEAGUES", system),
    ]:
        if not group:
            continue

        print()
        print(heading)
        print("-" * 92)
        print(
            f"{'League':34} "
            f"{'Rank':>12} "
            f"{'Previous':>10} "
            f"{'Move':>12} "
            f"{'Type':>10}"
        )
        print("-" * 92)

        for league in sorted(
            group,
            key=lambda l: (
                l.get("entry_rank") is None,
                l.get("entry_rank") or 999999999,
            ),
        ):
            rank = league.get("entry_rank")
            previous = league.get("entry_last_rank")

            if rank:
                try:
                    row = find_entry_on_league_page(
                        league["id"],
                        ENTRY_ID,
                        rank,
                    )
                    if row:
                        rank = row.get("rank", rank)
                        previous = row.get("last_rank", previous)
                except requests.RequestException:
                    pass

            league_size = None
            if league.get("league_type") == "x":
                try:
                    league_size = get_private_league_size(league["id"])
                except requests.RequestException:
                    pass

            if rank and league_size:
                rank_text = f"{rank:,} / {league_size:,}"
            elif rank:
                rank_text = f"{rank:,}"
            else:
                rank_text = "-"

            previous_text = f"{previous:,}" if previous else "-"
            league_type = (
                "Private"
                if league.get("league_type") == "x"
                else "System"
            )

            print(
                f"{league.get('name', 'Unknown')[:34]:34} "
                f"{rank_text:>12} "
                f"{previous_text:>10} "
                f"{movement(rank, previous):>12} "
                f"{league_type:>10}"
            )


def main():
    entry = get_entry()
    history = get_entry_history()
    current = history.get("current", [])
    event_info = get_latest_finished_event()

    latest = None
    previous = None

    if current:
        latest_event = event_info["id"] if event_info else None

        if latest_event is not None:
            latest = next(
                (row for row in current if row.get("event") == latest_event),
                None,
            )

        if latest is None:
            latest = max(current, key=lambda row: row.get("event", 0))

        previous = next(
            (
                row for row in current
                if row.get("event") == latest["event"] - 1
            ),
            None,
        )

    print_summary(entry, latest, previous, event_info)
    print_leagues(entry)

    print()
    print(
        "Run this whenever you want a performance check. "
        "The same data can later feed the web dashboard."
    )
    print()


if __name__ == "__main__":
    main()
