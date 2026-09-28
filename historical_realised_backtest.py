from itertools import combinations
from pathlib import Path
from statistics import mean

import pulp

from historical_chip_features import (
    historical_chip_features,
)
from historical_outcome_importer import (
    load_historical_player_gameweek,
)
from history_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_database,
)


BUDGET = 1000
POSITION_LIMITS = {
    "GKP": 2,
    "DEF": 5,
    "MID": 5,
    "FWD": 3,
}
STARTER_MINIMUMS = {
    "GKP": 1,
    "DEF": 3,
    "MID": 2,
    "FWD": 1,
}
STARTER_MAXIMUMS = {
    "GKP": 1,
    "DEF": 5,
    "MID": 5,
    "FWD": 3,
}
SIGNAL_KEYS = {
    "FH": "free_hit_signal",
    "BB": "bench_boost_signal",
    "TC": "triple_captain_signal",
}
TC_CAPTAINABLE_POOL_SIZE = 20
RECENT_FORM_GAMEWEEKS = 5
PLAYER_POOL_RECENCY_GAMEWEEKS = 3
SMALL_SAMPLE_SEASON_APPEARANCES = 5
SMALL_SAMPLE_RECENT_APPEARANCES = 2


def _normalise_position(position):
    position = str(
        position or ""
    ).upper()

    if position == "GK":
        return "GKP"

    return position


def _eligible_players(rows):
    result = []

    for row in rows:
        position = _normalise_position(
            row.get("position")
        )
        value = row.get("value")
        team = row.get("team_name")

        if (
            position
            not in POSITION_LIMITS
            or value is None
            or team is None
        ):
            continue

        result.append({
            **row,
            "position": position,
            "value": int(value),
            "total_points":
                int(
                    row.get(
                        "total_points",
                        0,
                    )
                    or 0
                ),
            "selected":
                int(
                    row.get(
                        "selected",
                        0,
                    )
                    or 0
                ),
        })

    return result


def _cbc_solver():
    system_cbc = Path(
        "/usr/bin/cbc"
    )

    if system_cbc.exists():
        return pulp.COIN_CMD(
            path=str(system_cbc),
            msg=False,
        )

    return pulp.PULP_CBC_CMD(
        msg=False
    )


def _normalise_team_key(value):
    return str(
        value or ""
    ).strip().casefold()


def _load_predeadline_player_history(
    season,
    gameweek,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                historical_player_gameweeks.fpl_element_id,
                historical_player_gameweeks.player_name,
                historical_player_gameweeks.position,
                historical_player_gameweeks.team_name,
                historical_player_gameweeks.total_points,
                historical_player_gameweeks.minutes,
                historical_player_gameweeks.value,
                historical_player_gameweeks.selected,
                historical_player_gameweeks.fixture_rows,
                gameweeks.gameweek
            FROM historical_player_gameweeks
            JOIN seasons
              ON seasons.id =
                 historical_player_gameweeks.season_id
            JOIN gameweeks
              ON gameweeks.id =
                 historical_player_gameweeks.gameweek_id
            WHERE seasons.season_key = ?
              AND gameweeks.gameweek < ?
            ORDER BY
                historical_player_gameweeks.fpl_element_id,
                gameweeks.gameweek
            """,
            (
                season,
                int(gameweek),
            ),
        ).fetchall()

    grouped = {}

    for row in rows:
        item = dict(row)
        grouped.setdefault(
            int(
                item[
                    "fpl_element_id"
                ]
            ),
            [],
        ).append(
            item
        )

    result = []
    recent_start = max(
        1,
        int(gameweek)
        - RECENT_FORM_GAMEWEEKS,
    )

    for element, history in (
        grouped.items()
    ):
        latest = history[-1]

        if (
            int(gameweek)
            - int(
                latest[
                    "gameweek"
                ]
            )
            > PLAYER_POOL_RECENCY_GAMEWEEKS
        ):
            continue

        recent = [
            row
            for row in history
            if int(
                row["gameweek"]
            ) >= recent_start
        ]
        season_appearances = sum(
            1
            for row in history
            if int(
                row.get("minutes", 0)
                or 0
            ) > 0
        )
        recent_appearances = sum(
            1
            for row in recent
            if int(
                row.get("minutes", 0)
                or 0
            ) > 0
        )

        result.append({
            "fpl_element_id":
                element,
            "player_name":
                latest["player_name"],
            "position":
                latest["position"],
            "team_name":
                latest["team_name"],
            "value":
                latest["value"],
            "selected":
                latest["selected"],
            "last_gameweek":
                int(
                    latest[
                        "gameweek"
                    ]
                ),
            "season_points":
                sum(
                    int(
                        row.get(
                            "total_points",
                            0,
                        )
                        or 0
                    )
                    for row in history
                ),
            "season_appearances":
                season_appearances,
            "recent_points":
                sum(
                    int(
                        row.get(
                            "total_points",
                            0,
                        )
                        or 0
                    )
                    for row in recent
                ),
            "recent_appearances":
                recent_appearances,
            "recent_minutes":
                sum(
                    int(
                        row.get(
                            "minutes",
                            0,
                        )
                        or 0
                    )
                    for row in recent
                ),
        })

    return result


def _load_team_fixture_projections(
    season,
    gameweek,
    db_path=DEFAULT_DB_PATH,
):
    ensure_database(
        db_path
    )

    with connect(
        db_path
    ) as connection:
        teams = connection.execute(
            """
            SELECT
                teams.id,
                teams.fpl_team_id,
                teams.name,
                teams.short_name
            FROM teams
            JOIN seasons
              ON seasons.id = teams.season_id
            WHERE seasons.season_key = ?
            """,
            (
                season,
            ),
        ).fetchall()
        fixtures = connection.execute(
            """
            SELECT
                fixtures.home_team_id,
                fixtures.away_team_id,
                fixtures.home_difficulty,
                fixtures.away_difficulty
            FROM fixtures
            JOIN seasons
              ON seasons.id = fixtures.season_id
            JOIN gameweeks
              ON gameweeks.id = fixtures.gameweek_id
            WHERE seasons.season_key = ?
              AND gameweeks.gameweek = ?
            """,
            (
                season,
                int(gameweek),
            ),
        ).fetchall()

    by_team_id = {
        int(team["id"]): {
            "fixture_qualities": [],
        }
        for team in teams
    }

    for fixture in fixtures:
        for side in (
            "home",
            "away",
        ):
            team_id = fixture[
                f"{side}_team_id"
            ]

            if team_id is None:
                continue

            context = by_team_id.get(
                int(team_id)
            )

            if context is None:
                continue

            difficulty = fixture[
                f"{side}_difficulty"
            ]
            difficulty = (
                3
                if difficulty is None
                else max(
                    1,
                    min(
                        5,
                        int(difficulty),
                    ),
                )
            )
            context[
                "fixture_qualities"
            ].append(
                (
                    5
                    - difficulty
                )
                / 4
            )

    result = {}

    for team in teams:
        context = by_team_id[
            int(team["id"])
        ]
        projection = {
            "fixture_count":
                len(
                    context[
                        "fixture_qualities"
                    ]
                ),
            "fixture_qualities":
                list(
                    context[
                        "fixture_qualities"
                    ]
                ),
        }

        for alias in (
            team["id"],
            team["fpl_team_id"],
            team["name"],
            team["short_name"],
        ):
            key = _normalise_team_key(
                alias
            )

            if key:
                result[key] = projection

    return result


def _prepare_predeadline_players(
    history,
    fixture_projections,
    target_rows,
):
    target_by_element = {
        int(row["fpl_element_id"]):
            row
        for row in target_rows
        if row.get(
            "fpl_element_id"
        ) is not None
    }
    max_selected = max(
        (
            int(
                row.get("selected", 0)
                or 0
            )
            for row in history
        ),
        default=0,
    )
    players = []
    unresolved_teams = set()

    for row in history:
        target = target_by_element.get(
            int(
                row[
                    "fpl_element_id"
                ]
            ),
            {},
        )
        team_name = (
            target.get(
                "team_name"
            )
            or row.get(
                "team_name"
            )
        )
        team_key = _normalise_team_key(
            team_name
        )
        fixture = fixture_projections.get(
            team_key
        )

        if fixture is None:
            unresolved_teams.add(
                str(
                    team_name
                )
            )
            continue
        season_appearances = max(
            1,
            int(
                row.get(
                    "season_appearances",
                    0,
                )
                or 0
            ),
        )
        recent_appearances = max(
            1,
            int(
                row.get(
                    "recent_appearances",
                    0,
                )
                or 0
            ),
        )
        season_ppg = (
            float(
                row.get(
                    "season_points",
                    0,
                )
                or 0
            )
            / season_appearances
        )
        recent_ppg = (
            float(
                row.get(
                    "recent_points",
                    0,
                )
                or 0
            )
            / recent_appearances
        )
        recent_minutes = float(
            row.get(
                "recent_minutes",
                0,
            )
            or 0
        )
        availability = (
            0.35
            + 0.65
            * min(
                1.0,
                recent_minutes
                / (
                    90
                    * recent_appearances
                ),
            )
        )
        fixture_factor = sum(
            0.75
            + 0.5 * quality
            for quality in fixture[
                "fixture_qualities"
            ]
        )
        ownership_share = (
            int(
                row.get("selected", 0)
                or 0
            )
            / max_selected
            if max_selected
            else 0.0
        )
        projection = (
            (
                0.55 * season_ppg
                + 0.45 * recent_ppg
            )
            * availability
            * fixture_factor
            + 0.5
            * ownership_share
            * min(
                1,
                fixture[
                    "fixture_count"
                ],
            )
        )

        players.append({
            **row,
            "team_name":
                team_name,
            "total_points":
                int(
                    target.get(
                        "total_points",
                        0,
                    )
                    or 0
                ),
            "minutes":
                int(
                    target.get(
                        "minutes",
                        0,
                    )
                    or 0
                ),
            "fixture_rows":
                int(
                    fixture[
                        "fixture_count"
                    ]
                ),
            "projection":
                round(
                    projection,
                    4,
                ),
        })

    return {
        "players":
            _eligible_players(
                players
            ),
        "unresolved_teams":
            sorted(
                unresolved_teams
            ),
    }


def _solve_realised_squad(
    rows,
    mode,
):
    players = _eligible_players(
        rows
    )

    if not players:
        return None

    mode = str(mode).upper()

    if mode not in {
        "FH",
        "BB",
    }:
        raise ValueError(
            "Realised squad optimisation "
            "supports FH or BB."
        )

    problem = pulp.LpProblem(
        f"historical_{mode.lower()}",
        pulp.LpMaximize,
    )

    selected = {
        index: pulp.LpVariable(
            f"selected_{index}",
            cat="Binary",
        )
        for index in range(
            len(players)
        )
    }
    captain = {
        index: pulp.LpVariable(
            f"captain_{index}",
            cat="Binary",
        )
        for index in range(
            len(players)
        )
    }

    starters = None

    if mode == "FH":
        starters = {
            index: pulp.LpVariable(
                f"starter_{index}",
                cat="Binary",
            )
            for index in range(
                len(players)
            )
        }

    problem += (
        pulp.lpSum(
            selected.values()
        )
        == 15
    )

    problem += (
        pulp.lpSum(
            int(
                players[index][
                    "value"
                ]
            )
            * selected[index]
            for index in selected
        )
        <= BUDGET
    )

    for position, count in (
        POSITION_LIMITS.items()
    ):
        problem += (
            pulp.lpSum(
                selected[index]
                for index, player
                in enumerate(players)
                if player[
                    "position"
                ] == position
            )
            == count
        )

    teams = {
        player["team_name"]
        for player in players
    }

    for team in teams:
        problem += (
            pulp.lpSum(
                selected[index]
                for index, player
                in enumerate(players)
                if player[
                    "team_name"
                ] == team
            )
            <= 3
        )

    problem += (
        pulp.lpSum(
            captain.values()
        )
        == 1
    )

    for index in selected:
        problem += (
            captain[index]
            <= selected[index]
        )

    if mode == "FH":
        problem += (
            pulp.lpSum(
                starters.values()
            )
            == 11
        )

        for index in selected:
            problem += (
                starters[index]
                <= selected[index]
            )
            problem += (
                captain[index]
                <= starters[index]
            )

        for position in (
            POSITION_LIMITS
        ):
            position_starters = (
                pulp.lpSum(
                    starters[index]
                    for index, player
                    in enumerate(players)
                    if player[
                        "position"
                    ] == position
                )
            )

            problem += (
                position_starters
                >= STARTER_MINIMUMS[
                    position
                ]
            )
            problem += (
                position_starters
                <= STARTER_MAXIMUMS[
                    position
                ]
            )

        problem += (
            pulp.lpSum(
                players[index][
                    "total_points"
                ]
                * starters[index]
                for index in starters
            )
            + pulp.lpSum(
                players[index][
                    "total_points"
                ]
                * captain[index]
                for index in captain
            )
        )
    else:
        problem += (
            pulp.lpSum(
                players[index][
                    "total_points"
                ]
                * selected[index]
                for index in selected
            )
            + pulp.lpSum(
                players[index][
                    "total_points"
                ]
                * captain[index]
                for index in captain
            )
        )

    status = problem.solve(
        _cbc_solver()
    )

    if pulp.LpStatus[
        status
    ] != "Optimal":
        return None

    picked = [
        players[index]
        for index in selected
        if pulp.value(
            selected[index]
        ) > 0.5
    ]

    captain_player = next(
        (
            players[index]
            for index in captain
            if pulp.value(
                captain[index]
            ) > 0.5
        ),
        None,
    )

    if mode == "FH":
        starter_rows = [
            players[index]
            for index in starters
            if pulp.value(
                starters[index]
            ) > 0.5
        ]

        starter_points = sum(
            player["total_points"]
            for player in starter_rows
        )
        captain_points = (
            captain_player[
                "total_points"
            ]
            if captain_player
            else 0
        )

        return {
            "score":
                starter_points
                + captain_points,
            "starter_points":
                starter_points,
            "captain_points":
                captain_points,
            "captain":
                (
                    captain_player[
                        "player_name"
                    ]
                    if captain_player
                    else None
                ),
            "squad_cost":
                sum(
                    player["value"]
                    for player in picked
                ),
            "starters":
                starter_rows,
            "squad":
                picked,
        }

    selected_points = sum(
        player["total_points"]
        for player in picked
    )
    captain_points = (
        captain_player[
            "total_points"
        ]
        if captain_player
        else 0
    )

    best_lineup = _best_lineup_from_squad(
        picked
    )

    return {
        "score":
            selected_points
            + captain_points,
        "selected_points":
            selected_points,
        "captain_points":
            captain_points,
        "bench_points":
            (
                selected_points
                - best_lineup[
                    "starter_points"
                ]
            ),
        "captain":
            (
                captain_player[
                    "player_name"
                ]
                if captain_player
                else None
            ),
        "squad_cost":
            sum(
                player["value"]
                for player in picked
            ),
    }


def _best_lineup_from_squad(
    squad,
):
    best = None

    for indices in combinations(
        range(len(squad)),
        11,
    ):
        starters = [
            squad[index]
            for index in indices
        ]

        counts = {
            position: 0
            for position in (
                POSITION_LIMITS
            )
        }

        for player in starters:
            counts[
                player["position"]
            ] += 1

        if any(
            counts[position]
            < STARTER_MINIMUMS[
                position
            ]
            or counts[position]
            > STARTER_MAXIMUMS[
                position
            ]
            for position in counts
        ):
            continue

        points = sum(
            player["total_points"]
            for player in starters
        )

        if (
            best is None
            or points
            > best[
                "starter_points"
            ]
        ):
            best = {
                "starter_points":
                    points,
            }

    return best or {
        "starter_points": 0,
    }


def _score_fixed_squad(
    squad,
):
    best_lineup = None

    for indices in combinations(
        range(len(squad)),
        11,
    ):
        starters = [
            squad[index]
            for index in indices
        ]

        counts = {
            position: 0
            for position in (
                POSITION_LIMITS
            )
        }

        for player in starters:
            counts[
                player["position"]
            ] += 1

        if any(
            counts[position]
            < STARTER_MINIMUMS[
                position
            ]
            or counts[position]
            > STARTER_MAXIMUMS[
                position
            ]
            for position in counts
        ):
            continue

        starter_points = sum(
            player["total_points"]
            for player in starters
        )
        captain = max(
            starters,
            key=lambda player:
                player[
                    "total_points"
                ],
        )
        score = (
            starter_points
            + captain[
                "total_points"
            ]
        )

        if (
            best_lineup is None
            or score
            > best_lineup[
                "score"
            ]
        ):
            best_lineup = {
                "score":
                    score,
                "starter_points":
                    starter_points,
                "captain_points":
                    captain[
                        "total_points"
                    ],
                "captain":
                    captain[
                        "player_name"
                    ],
                "starters":
                    starters,
            }

    return best_lineup


def _solve_template_squad(
    rows,
):
    players = _eligible_players(
        rows
    )

    if not players:
        return None

    problem = pulp.LpProblem(
        "historical_template_squad",
        pulp.LpMaximize,
    )

    selected = {
        index: pulp.LpVariable(
            f"template_{index}",
            cat="Binary",
        )
        for index in range(
            len(players)
        )
    }

    problem += (
        pulp.lpSum(
            selected.values()
        )
        == 15
    )

    problem += (
        pulp.lpSum(
            players[index][
                "value"
            ]
            * selected[index]
            for index in selected
        )
        <= BUDGET
    )

    for position, count in (
        POSITION_LIMITS.items()
    ):
        problem += (
            pulp.lpSum(
                selected[index]
                for index, player
                in enumerate(players)
                if player[
                    "position"
                ] == position
            )
            == count
        )

    teams = {
        player["team_name"]
        for player in players
    }

    for team in teams:
        problem += (
            pulp.lpSum(
                selected[index]
                for index, player
                in enumerate(players)
                if player[
                    "team_name"
                ] == team
            )
            <= 3
        )

    problem += pulp.lpSum(
        players[index][
            "selected"
        ]
        * selected[index]
        for index in selected
    )

    status = problem.solve(
        _cbc_solver()
    )

    if pulp.LpStatus[
        status
    ] != "Optimal":
        return None

    squad = [
        players[index]
        for index in selected
        if pulp.value(
            selected[index]
        ) > 0.5
    ]

    score = _score_fixed_squad(
        squad
    )

    if score is None:
        return None

    return {
        **score,
        "squad_cost":
            sum(
                player["value"]
                for player in squad
            ),
        "ownership_total":
            sum(
                player["selected"]
                for player in squad
            ),
        "squad":
            squad,
    }


def _score_predeadline_lineup(
    squad,
):
    best = None

    for indices in combinations(
        range(len(squad)),
        11,
    ):
        starters = [
            squad[index]
            for index in indices
        ]
        counts = {
            position: 0
            for position in (
                POSITION_LIMITS
            )
        }

        for player in starters:
            counts[
                player["position"]
            ] += 1

        if any(
            counts[position]
            < STARTER_MINIMUMS[
                position
            ]
            or counts[position]
            > STARTER_MAXIMUMS[
                position
            ]
            for position in counts
        ):
            continue

        captain = max(
            starters,
            key=lambda player: (
                player[
                    "projection"
                ],
                player[
                    "selected"
                ],
                player[
                    "player_name"
                ],
            ),
        )
        projected_score = (
            sum(
                player[
                    "projection"
                ]
                for player in starters
            )
            + captain[
                "projection"
            ]
        )
        ownership_total = sum(
            player["selected"]
            for player in starters
        )

        if (
            best is None
            or (
                projected_score,
                ownership_total,
            )
            > (
                best[
                    "projected_score"
                ],
                best[
                    "starter_ownership"
                ],
            )
        ):
            starter_points = sum(
                player[
                    "total_points"
                ]
                for player in starters
            )
            captain_points = captain[
                "total_points"
            ]
            best = {
                "score":
                    starter_points
                    + captain_points,
                "starter_points":
                    starter_points,
                "captain_points":
                    captain_points,
                "captain":
                    captain[
                        "player_name"
                    ],
                "projected_score":
                    round(
                        projected_score,
                        2,
                    ),
                "starter_ownership":
                    ownership_total,
                "starters":
                    starters,
            }

    return best


def _solve_projected_free_hit(
    rows,
):
    players = _eligible_players(
        rows
    )

    if not players:
        return None

    problem = pulp.LpProblem(
        "historical_predeadline_fh",
        pulp.LpMaximize,
    )
    selected = {
        index: pulp.LpVariable(
            f"fh_selected_{index}",
            cat="Binary",
        )
        for index in range(
            len(players)
        )
    }
    starters = {
        index: pulp.LpVariable(
            f"fh_starter_{index}",
            cat="Binary",
        )
        for index in range(
            len(players)
        )
    }
    captain = {
        index: pulp.LpVariable(
            f"fh_captain_{index}",
            cat="Binary",
        )
        for index in range(
            len(players)
        )
    }

    problem += (
        pulp.lpSum(
            selected.values()
        )
        == 15
    )
    problem += (
        pulp.lpSum(
            starters.values()
        )
        == 11
    )
    problem += (
        pulp.lpSum(
            captain.values()
        )
        == 1
    )
    problem += (
        pulp.lpSum(
            players[index][
                "value"
            ]
            * selected[index]
            for index in selected
        )
        <= BUDGET
    )

    for index, selected_variable in (
        selected.items()
    ):
        problem += (
            starters[index]
            <= selected_variable
        )
        problem += (
            captain[index]
            <= starters[index]
        )

    for position, count in (
        POSITION_LIMITS.items()
    ):
        problem += (
            pulp.lpSum(
                selected[index]
                for index, player
                in enumerate(players)
                if player[
                    "position"
                ] == position
            )
            == count
        )
        position_starters = (
            pulp.lpSum(
                starters[index]
                for index, player
                in enumerate(players)
                if player[
                    "position"
                ] == position
            )
        )
        problem += (
            position_starters
            >= STARTER_MINIMUMS[
                position
            ]
        )
        problem += (
            position_starters
            <= STARTER_MAXIMUMS[
                position
            ]
        )

    teams = {
        player["team_name"]
        for player in players
    }

    for team in teams:
        problem += (
            pulp.lpSum(
                selected[index]
                for index, player
                in enumerate(players)
                if player[
                    "team_name"
                ] == team
            )
            <= 3
        )

    problem += (
        pulp.lpSum(
            players[index][
                "projection"
            ]
            * starters[index]
            for index in starters
        )
        + pulp.lpSum(
            players[index][
                "projection"
            ]
            * captain[index]
            for index in captain
        )
    )

    status = problem.solve(
        _cbc_solver()
    )

    if pulp.LpStatus[
        status
    ] != "Optimal":
        return None

    squad = [
        players[index]
        for index in selected
        if pulp.value(
            selected[index]
        ) > 0.5
    ]
    starter_rows = [
        players[index]
        for index in starters
        if pulp.value(
            starters[index]
        ) > 0.5
    ]
    captain_player = next(
        (
            players[index]
            for index in captain
            if pulp.value(
                captain[index]
            ) > 0.5
        ),
        None,
    )

    if captain_player is None:
        return None

    starter_points = sum(
        player["total_points"]
        for player in starter_rows
    )
    captain_points = captain_player[
        "total_points"
    ]

    return {
        "score":
            starter_points
            + captain_points,
        "starter_points":
            starter_points,
        "captain_points":
            captain_points,
        "captain":
            captain_player[
                "player_name"
            ],
        "projected_score":
            round(
                sum(
                    player[
                        "projection"
                    ]
                    for player in starter_rows
                )
                + captain_player[
                    "projection"
                ],
                2,
            ),
        "squad_cost":
            sum(
                player["value"]
                for player in squad
            ),
        "starters":
            starter_rows,
        "squad":
            squad,
    }


def _predeadline_fh_outcome(
    season,
    gameweek,
    target_rows,
    db_path=DEFAULT_DB_PATH,
):
    history = (
        _load_predeadline_player_history(
            season,
            gameweek,
            db_path=db_path,
        )
    )
    fixture_projections = (
        _load_team_fixture_projections(
            season,
            gameweek,
            db_path=db_path,
        )
    )
    prepared = (
        _prepare_predeadline_players(
            history,
            fixture_projections,
            target_rows,
        )
    )
    players = prepared[
        "players"
    ]

    if len(players) < 15:
        return None

    template_selection = (
        _solve_template_squad(
            players
        )
    )
    free_hit = (
        _solve_projected_free_hit(
            players
        )
    )

    if (
        template_selection is None
        or free_hit is None
    ):
        return None

    template = (
        _score_predeadline_lineup(
            template_selection[
                "squad"
            ]
        )
    )

    if template is None:
        return None

    template.update({
        "squad_cost":
            template_selection[
                "squad_cost"
            ],
        "ownership_total":
            template_selection[
                "ownership_total"
            ],
        "squad":
            template_selection[
                "squad"
            ],
    })
    omniscient = (
        _solve_realised_squad(
            target_rows,
            "FH",
        )
    )

    return {
        "free_hit":
            free_hit,
        "template":
            template,
        "omniscient":
            omniscient,
        "players":
            players,
        "unresolved_teams":
            prepared[
                "unresolved_teams"
            ],
    }


def _player_diagnostic(
    player,
):
    return {
        "player":
            player[
                "player_name"
            ],
        "position":
            player[
                "position"
            ],
        "team":
            player[
                "team_name"
            ],
        "points":
            player[
                "total_points"
            ],
        "fixture_rows":
            int(
                player.get(
                    "fixture_rows",
                    0,
                )
                or 0
            ),
        "value":
            player[
                "value"
            ],
        "selected":
            player[
                "selected"
            ],
        "season_appearances":
            int(
                player.get(
                    "season_appearances",
                    0,
                )
                or 0
            ),
        "recent_appearances":
            int(
                player.get(
                    "recent_appearances",
                    0,
                )
                or 0
            ),
        "recent_minutes":
            int(
                player.get(
                    "recent_minutes",
                    0,
                )
                or 0
            ),
        "projection":
            (
                round(
                    float(
                        player[
                            "projection"
                        ]
                    ),
                    2,
                )
                if "projection"
                in player
                else None
            ),
    }


def _captain_sanity(
    captain,
    players,
):
    candidates = [
        player
        for player in _eligible_players(
            players
        )
        if int(
            player.get(
                "fixture_rows",
                0,
            )
            or 0
        ) > 0
    ]
    captain_player = next(
        (
            player
            for player in candidates
            if player[
                "player_name"
            ] == captain
        ),
        None,
    )

    if captain_player is None:
        return None

    selected = int(
        captain_player.get(
            "selected",
            0,
        )
        or 0
    )

    return {
        **_player_diagnostic(
            captain_player
        ),
        "ownership_rank":
            1
            + sum(
                1
                for player in candidates
                if int(
                    player.get(
                        "selected",
                        0,
                    )
                    or 0
                ) > selected
            ),
        "candidate_count":
            len(candidates),
    }


def _lineup_diagnostic(
    players,
):
    small_sample_players = [
        player[
            "player_name"
        ]
        for player in players
        if (
            int(
                player.get(
                    "season_appearances",
                    0,
                )
                or 0
            )
            < SMALL_SAMPLE_SEASON_APPEARANCES
            or int(
                player.get(
                    "recent_appearances",
                    0,
                )
                or 0
            )
            < SMALL_SAMPLE_RECENT_APPEARANCES
        )
    ]

    return {
        "player_count":
            len(players),
        "player_fixtures":
            sum(
                int(
                    player.get(
                        "fixture_rows",
                        0,
                    )
                    or 0
                )
                for player in players
            ),
        "zero_fixture_players":
            sum(
                1
                for player in players
                if int(
                    player.get(
                        "fixture_rows",
                        0,
                    )
                    or 0
                ) == 0
            ),
        "small_sample_players":
            sorted(
                small_sample_players
            ),
        "players": [
            _player_diagnostic(
                player
            )
            for player in sorted(
                players,
                key=lambda row: (
                    row["position"],
                    -row["total_points"],
                    row["player_name"],
                ),
            )
        ],
    }


def _fh_outcome_detail(
    outcome,
    baseline,
    players,
    omniscient=None,
    unresolved_teams=None,
):
    eligible = _eligible_players(
        players
    )
    zero_fixture_pool_players = sum(
        1
        for player in eligible
        if int(
            player.get(
                "fixture_rows",
                0,
            )
            or 0
        ) == 0
    )

    return {
        "free_hit": {
            key: value
            for key, value
            in outcome.items()
            if key not in {
                "starters",
                "squad",
            }
        },
        "template": {
            key: value
            for key, value
            in baseline.items()
            if key not in {
                "starters",
                "squad",
            }
        },
        "free_hit_xi":
            _lineup_diagnostic(
                outcome[
                    "starters"
                ]
            ),
        "template_xi":
            _lineup_diagnostic(
                baseline[
                    "starters"
                ]
            ),
        "captain_sanity": {
            "free_hit":
                _captain_sanity(
                    outcome.get(
                        "captain"
                    ),
                    eligible,
                ),
            "template":
                _captain_sanity(
                    baseline.get(
                        "captain"
                    ),
                    eligible,
                ),
        },
        "player_pool": {
            "eligible_players":
                len(eligible),
            "zero_fixture_players":
                zero_fixture_pool_players,
            "can_measure_template_blankers":
                zero_fixture_pool_players
                > 0,
            "unresolved_teams":
                list(
                    unresolved_teams
                    or []
                ),
        },
        "omniscient":
            (
                {
                    "score":
                        omniscient[
                            "score"
                        ],
                    "uplift_over_template":
                        float(
                            omniscient[
                                "score"
                            ]
                            - baseline[
                                "score"
                            ]
                        ),
                }
                if omniscient
                is not None
                else None
            ),
    }


def _tc_realised_ceiling(rows):
    eligible = [
        {
            **row,
            "selected":
                int(
                    row.get(
                        "selected",
                        0,
                    )
                    or 0
                ),
        }
        for row in rows
        if int(
            row.get(
                "minutes",
                0,
            )
            or 0
        ) > 0
    ]

    if not eligible:
        return None

    captainable = sorted(
        eligible,
        key=lambda row: (
            -row["selected"],
            -int(
                row.get(
                    "value",
                    0,
                )
                or 0
            ),
            row[
                "player_name"
            ],
        ),
    )[
        :TC_CAPTAINABLE_POOL_SIZE
    ]

    player = max(
        captainable,
        key=lambda row:
            int(
                row.get(
                    "total_points",
                    0,
                )
                or 0
            ),
    )

    return {
        "score":
            int(
                player[
                    "total_points"
                ]
            ),
        "player":
            player[
                "player_name"
            ],
        "selected":
            player[
                "selected"
            ],
        "pool_size":
            len(
                captainable
            ),
    }


def _rankdata(values):
    order = sorted(
        range(len(values)),
        key=lambda index:
            values[index],
    )
    ranks = [
        0.0
        for _ in values
    ]
    cursor = 0

    while cursor < len(order):
        end = cursor

        while (
            end + 1
            < len(order)
            and values[
                order[end + 1]
            ]
            == values[
                order[cursor]
            ]
        ):
            end += 1

        rank = (
            cursor
            + end
            + 2
        ) / 2

        for offset in range(
            cursor,
            end + 1,
        ):
            ranks[
                order[offset]
            ] = rank

        cursor = end + 1

    return ranks


def _pearson(left, right):
    if (
        len(left) < 2
        or len(left)
        != len(right)
    ):
        return None

    left_mean = mean(left)
    right_mean = mean(right)

    numerator = sum(
        (
            a - left_mean
        )
        * (
            b - right_mean
        )
        for a, b
        in zip(
            left,
            right,
        )
    )
    left_sum = sum(
        (
            value
            - left_mean
        ) ** 2
        for value in left
    )
    right_sum = sum(
        (
            value
            - right_mean
        ) ** 2
        for value in right
    )

    denominator = (
        left_sum
        * right_sum
    ) ** 0.5

    if denominator == 0:
        return None

    return (
        numerator
        / denominator
    )


def _spearman(left, right):
    correlation = _pearson(
        _rankdata(left),
        _rankdata(right),
    )

    if correlation is None:
        return None

    return round(
        correlation,
        3,
    )


def _outcome_for_chip(
    chip,
    rows,
    season=None,
    gameweek=None,
    db_path=DEFAULT_DB_PATH,
):
    if chip == "TC":
        outcome = (
            _tc_realised_ceiling(
                rows
            )
        )

        if outcome is None:
            return None

        return {
            "metric":
                "tc_captainable_increment_ceiling",
            "value":
                float(
                    outcome[
                        "score"
                    ]
                ),
            "detail":
                outcome[
                    "player"
                ],
        }

    if chip == "FH":
        if (
            season is None
            or gameweek is None
        ):
            return None

        comparison = (
            _predeadline_fh_outcome(
                season,
                gameweek,
                rows,
                db_path=db_path,
            )
        )

        if comparison is None:
            return None

        outcome = comparison[
            "free_hit"
        ]
        baseline = comparison[
            "template"
        ]

        return {
            "metric":
                "fh_predeadline_proxy_uplift",
            "value":
                float(
                    outcome[
                        "score"
                    ]
                    - baseline[
                        "score"
                    ]
                ),
            "detail":
                _fh_outcome_detail(
                    outcome,
                    baseline,
                    comparison[
                        "players"
                    ],
                    omniscient=comparison[
                        "omniscient"
                    ],
                    unresolved_teams=comparison[
                        "unresolved_teams"
                    ],
                ),
        }

    if chip == "BB":
        outcome = (
            _solve_realised_squad(
                rows,
                "BB",
            )
        )

        if outcome is None:
            return None

        return {
            "metric":
                "bb_bench_ceiling",
            "value":
                float(
                    outcome[
                        "bench_points"
                    ]
                ),
            "detail":
                outcome,
        }

    raise ValueError(
        "Outcome backtest supports "
        "FH, BB and TC."
    )


def _case_summary(cases):
    signals = [
        row["signal"]
        for row in cases
    ]
    outcomes = [
        row["outcome"]
        for row in cases
    ]

    return {
        "case_count":
            len(cases),
        "spearman":
            _spearman(
                signals,
                outcomes,
            ),
        "outcome_mean":
            (
                round(
                    mean(outcomes),
                    2,
                )
                if outcomes
                else None
            ),
    }


def _fh_projection_summary(
    cases,
):
    comparable = [
        row
        for row in cases
        if row.get(
            "projected_uplift"
        ) is not None
    ]
    projected_uplifts = [
        row[
            "projected_uplift"
        ]
        for row in comparable
    ]
    outcomes = [
        row["outcome"]
        for row in comparable
    ]

    return {
        "projected_case_count":
            len(comparable),
        "projected_spearman":
            _spearman(
                projected_uplifts,
                outcomes,
            ),
        "projected_uplift_mean":
            (
                round(
                    mean(
                        projected_uplifts
                    ),
                    2,
                )
                if projected_uplifts
                else None
            ),
    }


def _fh_archetype_summaries(
    cases,
):
    definitions = (
        (
            "blank_only",
            "Blank-only",
            lambda row:
                row["kind"]
                == "blank",
        ),
        (
            "blank_double",
            "Mixed blank + double",
            lambda row:
                row["kind"]
                == "blank_double",
        ),
    )

    summaries = []

    for key, label, predicate in (
        definitions
    ):
        matching = [
            row
            for row in cases
            if predicate(row)
        ]
        summary = _case_summary(
            matching
        )
        projection_summary = (
            _fh_projection_summary(
                matching
            )
        )
        summaries.append({
            "key":
                key,
            "label":
                label,
            **summary,
            **projection_summary,
        })

    return summaries


def _fh_extreme_diagnostics(
    cases,
    limit=10,
):
    diagnostics = []

    for case in sorted(
        cases,
        key=lambda row: (
            -row["outcome"],
            row["season"],
            row["gameweek"],
        ),
    )[:int(limit)]:
        detail = (
            case.get("detail")
            or {}
        )
        free_hit = (
            detail.get("free_hit")
            or {}
        )
        template = (
            detail.get("template")
            or {}
        )
        omniscient = (
            detail.get("omniscient")
            or {}
        )

        diagnostics.append({
            "season":
                case["season"],
            "gameweek":
                case["gameweek"],
            "kind":
                case["kind"],
            "signal":
                case["signal"],
            "uplift":
                case["outcome"],
            "template_score":
                template.get("score"),
            "free_hit_score":
                free_hit.get("score"),
            "template_captain":
                template.get("captain"),
            "free_hit_captain":
                free_hit.get("captain"),
            "template_projection":
                template.get(
                    "projected_score"
                ),
            "free_hit_projection":
                free_hit.get(
                    "projected_score"
                ),
            "omniscient_score":
                omniscient.get("score"),
            "omniscient_uplift":
                omniscient.get(
                    "uplift_over_template"
                ),
            "template_xi":
                detail.get("template_xi"),
            "free_hit_xi":
                detail.get("free_hit_xi"),
            "player_pool":
                detail.get("player_pool"),
            "captain_sanity":
                detail.get(
                    "captain_sanity"
                ),
        })

    return diagnostics


def backtest_historical_chip_outcomes(
    seasons,
    db_path=DEFAULT_DB_PATH,
):
    cache = {}
    chip_reports = []

    for chip in (
        "FH",
        "BB",
        "TC",
    ):
        signal_key = (
            SIGNAL_KEYS[
                chip
            ]
        )
        cases = []
        excluded_unplayable = []

        for season in seasons:
            feature_rows = (
                historical_chip_features(
                    season,
                    db_path=db_path,
                )
            )

            for feature in (
                feature_rows
            ):
                signal = float(
                    feature.get(
                        signal_key,
                        0.0,
                    )
                    or 0.0
                )

                if signal <= 0:
                    continue

                gameweek = int(
                    feature[
                        "gameweek"
                    ]
                )

                if (
                    chip == "FH"
                    and feature.get(
                        "scheduled_fixture_count"
                    ) == 0
                ):
                    excluded_unplayable.append({
                        "season":
                            season,
                        "gameweek":
                            gameweek,
                        "kind":
                            feature[
                                "kind"
                            ],
                        "signal":
                            signal,
                        "active_team_count":
                            int(
                                feature.get(
                                    "active_team_count",
                                    0,
                                )
                                or 0
                            ),
                        "scheduled_fixture_count":
                            0,
                        "reason":
                            "no scheduled fixtures",
                    })
                    continue

                key = (
                    season,
                    gameweek,
                    chip,
                )

                if key not in cache:
                    rows = (
                        load_historical_player_gameweek(
                            season,
                            gameweek,
                            db_path=db_path,
                        )
                    )
                    cache[key] = (
                        _outcome_for_chip(
                            chip,
                            rows,
                            season=season,
                            gameweek=gameweek,
                            db_path=db_path,
                        )
                    )

                outcome = cache[key]

                if outcome is None:
                    continue

                detail = outcome[
                    "detail"
                ]
                projected_uplift = None

                if (
                    chip == "FH"
                    and detail
                ):
                    free_hit = (
                        detail.get(
                            "free_hit"
                        )
                        or {}
                    )
                    template = (
                        detail.get(
                            "template"
                        )
                        or {}
                    )
                    if (
                        free_hit.get(
                            "projected_score"
                        ) is not None
                        and template.get(
                            "projected_score"
                        ) is not None
                    ):
                        projected_uplift = round(
                            float(
                                free_hit[
                                    "projected_score"
                                ]
                            )
                            - float(
                                template[
                                    "projected_score"
                                ]
                            ),
                            2,
                        )

                cases.append({
                    "season":
                        season,
                    "gameweek":
                        gameweek,
                    "kind":
                        feature[
                            "kind"
                        ],
                    "signal":
                        signal,
                    "outcome_metric":
                        outcome[
                            "metric"
                        ],
                    "outcome":
                        outcome[
                            "value"
                        ],
                    "detail":
                        detail,
                    "projected_uplift":
                        projected_uplift,
                })

        summary = _case_summary(
            cases
        )
        projection_summary = (
            _fh_projection_summary(
                cases
            )
            if chip == "FH"
            else None
        )

        strongest_signal = sorted(
            cases,
            key=lambda row: (
                -row["signal"],
                row["season"],
                row["gameweek"],
            ),
        )[:5]
        strongest_outcome = sorted(
            cases,
            key=lambda row: (
                -row["outcome"],
                row["season"],
                row["gameweek"],
            ),
        )[:5]

        chip_reports.append({
            "chip":
                chip,
            "case_count":
                summary[
                    "case_count"
                ],
            "metric":
                (
                    cases[0][
                        "outcome_metric"
                    ]
                    if cases
                    else None
                ),
            "spearman":
                summary[
                    "spearman"
                ],
            "outcome_mean":
                summary[
                    "outcome_mean"
                ],
            "projection_validation":
                projection_summary,
            "excluded_unplayable":
                excluded_unplayable,
            "archetypes":
                (
                    _fh_archetype_summaries(
                        cases
                    )
                    if chip == "FH"
                    else []
                ),
            "fh_diagnostics":
                (
                    _fh_extreme_diagnostics(
                        cases
                    )
                    if chip == "FH"
                    else []
                ),
            "strongest_signal":
                strongest_signal,
            "strongest_outcome":
                strongest_outcome,
            "cases":
                cases,
        })

    return {
        "seasons":
            list(seasons),
        "chips":
            chip_reports,
        "lookahead_safe":
            False,
        "note":
            (
                "This is a retrospective realised-opportunity "
                "calibration. FH squads and lineups are selected "
                "from prior-Gameweek ownership, form and fixture "
                "inputs before being scored with actual points; "
                "BB and TC remain outcome ceilings. Archived "
                "team-strength/FDR inputs have not yet been proven "
                "to be pre-deadline snapshots. Do not use this "
                "report alone to retune live decision thresholds."
            ),
    }
