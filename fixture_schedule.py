from collections import defaultdict


def build_fixture_calendar(
    fixtures,
    team_ids,
    start_gameweek=None,
    end_gameweek=None,
):
    """
    Return a Gameweek -> team -> [fixtures] mapping.

    Every requested team is present for every requested Gameweek,
    so a blank is represented by an empty list rather than a
    missing key. Multiple fixtures naturally represent a double
    (or, theoretically, a triple) Gameweek.
    """
    team_ids = list(team_ids)

    gameweeks = {
        fixture.get("event")
        for fixture in fixtures
        if fixture.get("event") is not None
    }

    if (
        start_gameweek is not None
        and end_gameweek is not None
    ):
        gameweeks.update(
            range(
                start_gameweek,
                end_gameweek + 1,
            )
        )

    calendar = {
        gameweek: {
            team_id: []
            for team_id in team_ids
        }
        for gameweek in sorted(gameweeks)
        if (
            (start_gameweek is None or gameweek >= start_gameweek)
            and
            (end_gameweek is None or gameweek <= end_gameweek)
        )
    }

    for fixture in fixtures:
        gameweek = fixture.get("event")

        if gameweek not in calendar:
            continue

        home_team = fixture["team_h"]
        away_team = fixture["team_a"]

        if home_team in calendar[gameweek]:
            calendar[gameweek][home_team].append(
                fixture
            )

        if away_team in calendar[gameweek]:
            calendar[gameweek][away_team].append(
                fixture
            )

    return calendar


def gameweek_fixture_counts(
    calendar,
    gameweek,
):
    return {
        team_id: len(fixtures)
        for team_id, fixtures
        in calendar.get(
            gameweek,
            {},
        ).items()
    }


def summarise_gameweek(
    calendar,
    gameweek,
):
    counts = gameweek_fixture_counts(
        calendar,
        gameweek,
    )

    blank_teams = sorted(
        team_id
        for team_id, count
        in counts.items()
        if count == 0
    )

    double_teams = sorted(
        team_id
        for team_id, count
        in counts.items()
        if count >= 2
    )

    if blank_teams and double_teams:
        kind = "blank_double"
    elif blank_teams:
        kind = "blank"
    elif double_teams:
        kind = "double"
    else:
        kind = "normal"

    return {
        "gameweek":
            gameweek,
        "kind":
            kind,
        "fixture_counts":
            counts,
        "blank_teams":
            blank_teams,
        "double_teams":
            double_teams,
        "blank_team_count":
            len(blank_teams),
        "double_team_count":
            len(double_teams),
        "max_fixtures":
            max(
                counts.values(),
                default=0,
            ),
    }


def summarise_calendar(
    calendar,
):
    return [
        summarise_gameweek(
            calendar,
            gameweek,
        )
        for gameweek in sorted(calendar)
    ]
