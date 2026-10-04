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
FH_CAPTAIN_OWNERSHIP_POOL_SIZE = 50
FORM_REGRESSION_POINTS_PER_APPEARANCE = 2.0
CALIBRATION_SEASON_APPEARANCES = 10
CALIBRATION_RECENT_MINUTES = 360
CALIBRATION_PROJECTION_CAP_QUANTILE = 0.9
SOFT_MONOTONIC_CALIBRATION_BLEND = 0.5
CALIBRATION_PROJECTION_BANDS = (
    (0.0, 4.0),
    (4.0, 6.0),
    (6.0, 8.0),
    (8.0, None),
)


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
        raw_season_appearances = int(
            row.get(
                "season_appearances",
                0,
            )
            or 0
        )
        raw_recent_appearances = int(
            row.get(
                "recent_appearances",
                0,
            )
            or 0
        )
        season_appearances = max(
            1,
            raw_season_appearances,
        )
        recent_appearances = max(
            1,
            raw_recent_appearances,
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
        regressed_season_ppg = (
            min(
                1.0,
                raw_season_appearances
                / SMALL_SAMPLE_SEASON_APPEARANCES,
            )
            * season_ppg
            + (
                1.0
                - min(
                    1.0,
                    raw_season_appearances
                    / SMALL_SAMPLE_SEASON_APPEARANCES,
                )
            )
            * FORM_REGRESSION_POINTS_PER_APPEARANCE
        )
        regressed_recent_ppg = (
            min(
                1.0,
                raw_recent_appearances
                / SMALL_SAMPLE_RECENT_APPEARANCES,
            )
            * recent_ppg
            + (
                1.0
                - min(
                    1.0,
                    raw_recent_appearances
                    / SMALL_SAMPLE_RECENT_APPEARANCES,
                )
            )
            * FORM_REGRESSION_POINTS_PER_APPEARANCE
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
        regressed_projection = (
            (
                0.55
                * regressed_season_ppg
                + 0.45
                * regressed_recent_ppg
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
            "regressed_projection":
                round(
                    regressed_projection,
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
    captain_pool=None,
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

        captain_candidates = [
            player
            for player in starters
            if (
                captain_pool is None
                or player[
                    "player_name"
                ] in captain_pool
            )
        ]

        if not captain_candidates:
            continue

        captain = max(
            captain_candidates,
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
                "starter_projected_score":
                    round(
                        sum(
                            player[
                                "projection"
                            ]
                            for player
                            in starters
                        ),
                        2,
                    ),
                "captain_projection":
                    round(
                        captain[
                            "projection"
                        ],
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
    captain_ownership_tiebreak=False,
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

    if captain_ownership_tiebreak:
        captain_player = max(
            starter_rows,
            key=lambda player: (
                float(
                    player.get(
                        "projection",
                        0.0,
                    )
                    or 0.0
                ),
                int(
                    player.get(
                        "selected",
                        0,
                    )
                    or 0
                ),
                player["player_name"],
            ),
        )

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
        "starter_projected_score":
            round(
                sum(
                    player[
                        "projection"
                    ]
                    for player
                    in starter_rows
                ),
                2,
            ),
        "captain_projection":
            round(
                captain_player[
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


def _captain_ownership_pool(
    players,
    size=FH_CAPTAIN_OWNERSHIP_POOL_SIZE,
):
    active = [
        player
        for player in players
        if int(
            player.get(
                "fixture_rows",
                0,
            )
            or 0
        ) > 0
    ]

    return {
        player[
            "player_name"
        ]
        for player in sorted(
            active,
            key=lambda row: (
                -int(
                    row.get(
                        "selected",
                        0,
                    )
                    or 0
                ),
                -float(
                    row.get(
                        "projection",
                        0.0,
                    )
                    or 0.0
                ),
                row[
                    "player_name"
                ],
            ),
        )[:int(size)]
    }


def _players_with_projection(
    players,
    projection_key,
):
    return [
        {
            **player,
            "projection":
                float(
                    player.get(
                        projection_key,
                        player.get(
                            "projection",
                            0.0,
                        ),
                    )
                    or 0.0
                ),
        }
        for player in players
    ]


def _remap_squad(
    squad,
    players,
):
    by_element = {
        int(
            player[
                "fpl_element_id"
            ]
        ):
            player
        for player in players
        if player.get(
            "fpl_element_id"
        ) is not None
    }

    return [
        by_element.get(
            int(
                player[
                    "fpl_element_id"
                ]
            ),
            player,
        )
        if player.get(
            "fpl_element_id"
        ) is not None
        else player
        for player in squad
    ]


def _fh_sensitivity_model(
    key,
    label,
    free_hit,
    template,
    note,
):
    if (
        free_hit is None
        or template is None
    ):
        return {
            "key": key,
            "label": label,
            "available": False,
            "note": note,
        }

    return {
        "key": key,
        "label": label,
        "available": True,
        "note": note,
        "projected_uplift":
            round(
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
            ),
        "realised_uplift":
            float(
                free_hit[
                    "score"
                ]
                - template[
                    "score"
                ]
            ),
        "starter_projected_uplift":
            round(
                float(
                    free_hit[
                        "starter_projected_score"
                    ]
                )
                - float(
                    template[
                        "starter_projected_score"
                    ]
                ),
                2,
            ),
        "captain_projected_uplift":
            round(
                float(
                    free_hit[
                        "captain_projection"
                    ]
                )
                - float(
                    template[
                        "captain_projection"
                    ]
                ),
                2,
            ),
        "free_hit_captain":
            free_hit[
                "captain"
            ],
        "template_captain":
            template[
                "captain"
            ],
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
    captain_pool = (
        _captain_ownership_pool(
            players
        )
    )
    captain_pool_free_hit = (
        _score_predeadline_lineup(
            free_hit[
                "squad"
            ],
            captain_pool=captain_pool,
        )
    )
    captain_pool_template = (
        _score_predeadline_lineup(
            template[
                "squad"
            ],
            captain_pool=captain_pool,
        )
    )
    history_floor_players = [
        player
        for player in players
        if (
            int(
                player.get(
                    "season_appearances",
                    0,
                )
                or 0
            )
            >= SMALL_SAMPLE_SEASON_APPEARANCES
            and int(
                player.get(
                    "recent_appearances",
                    0,
                )
                or 0
            )
            >= SMALL_SAMPLE_RECENT_APPEARANCES
        )
    ]
    history_floor_free_hit = (
        _solve_projected_free_hit(
            history_floor_players
        )
    )
    regressed_players = (
        _players_with_projection(
            players,
            "regressed_projection",
        )
    )
    regressed_free_hit = (
        _solve_projected_free_hit(
            regressed_players
        )
    )
    regressed_template = (
        _score_predeadline_lineup(
            _remap_squad(
                template[
                    "squad"
                ],
                regressed_players,
            )
        )
    )
    sensitivity_models = [
        _fh_sensitivity_model(
            "captain_pool_50",
            "Top-50 ownership captain rescore",
            captain_pool_free_hit,
            captain_pool_template,
            (
                "Rescores the selected squads and XIs with "
                "captaincy limited to the 50 most-owned active "
                "players."
            ),
        ),
        _fh_sensitivity_model(
            "history_floor",
            "Minimum history (5 season/2 recent)",
            history_floor_free_hit,
            template,
            (
                "FH candidates require at least five season and "
                "two recent appearances; the reconstructed "
                "template is unchanged."
            ),
        ),
        _fh_sensitivity_model(
            "regressed_form",
            "Regressed small samples (toward 2 PPG)",
            regressed_free_hit,
            regressed_template,
            (
                "Season and recent PPG are regressed toward two "
                "points per appearance until the appearance "
                "thresholds are met."
            ),
        ),
    ]

    return {
        "free_hit":
            free_hit,
        "regressed_free_hit":
            regressed_free_hit,
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
        "sensitivity_models":
            sensitivity_models,
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
    sensitivity_models=None,
    calibration_outcome=None,
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
    calibration_outcome = (
        calibration_outcome
        or outcome
    )
    free_hit_starters = {
        (
            player.get("fpl_element_id"),
            player.get("player_name"),
        )
        for player in calibration_outcome[
            "starters"
        ]
    }
    template_starters = {
        (
            player.get("fpl_element_id"),
            player.get("player_name"),
        )
        for player in baseline[
            "starters"
        ]
    }
    template_squad = {
        (
            player.get("fpl_element_id"),
            player.get("player_name"),
        )
        for player in baseline[
            "squad"
        ]
    }
    calibration_players = []

    for player in eligible:
        identity = (
            player.get("fpl_element_id"),
            player.get("player_name"),
        )
        calibration_players.append({
            "fpl_element_id":
                player.get(
                    "fpl_element_id"
                ),
            "player_name":
                player["player_name"],
            "position":
                player["position"],
            "team_name":
                player["team_name"],
            "value":
                player["value"],
            "selected":
                player["selected"],
            "total_points":
                player["total_points"],
            "fixture_rows":
                int(
                    player.get(
                        "fixture_rows",
                        0,
                    )
                    or 0
                ),
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
                float(
                    player.get(
                        "projection",
                        0.0,
                    )
                    or 0.0
                ),
            "regressed_projection":
                float(
                    player.get(
                        "regressed_projection",
                        player.get(
                            "projection",
                            0.0,
                        ),
                    )
                    or 0.0
                ),
            "free_hit_starter":
                identity
                in free_hit_starters,
            "template_starter":
                identity
                in template_starters,
            "template_squad":
                identity
                in template_squad,
        })

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
        "sensitivity_models":
            list(
                sensitivity_models
                or []
            ),
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
            "calibration_players":
                calibration_players,
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
                    sensitivity_models=comparison[
                        "sensitivity_models"
                    ],
                    calibration_outcome=comparison[
                        "regressed_free_hit"
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


def _fh_model_metrics(
    rows,
):
    available = [
        row
        for row in rows
        if (
            row.get(
                "projected_uplift"
            ) is not None
            and row.get(
                "realised_uplift"
            ) is not None
        )
    ]
    projected = [
        float(
            row[
                "projected_uplift"
            ]
        )
        for row in available
    ]
    realised = [
        float(
            row[
                "realised_uplift"
            ]
        )
        for row in available
    ]
    errors = [
        prediction - outcome
        for prediction, outcome
        in zip(
            projected,
            realised,
            strict=True,
        )
    ]
    starter_components = [
        float(
            row[
                "starter_projected_uplift"
            ]
        )
        for row in available
        if row.get(
            "starter_projected_uplift"
        ) is not None
    ]
    captain_components = [
        float(
            row[
                "captain_projected_uplift"
            ]
        )
        for row in available
        if row.get(
            "captain_projected_uplift"
        ) is not None
    ]

    return {
        "case_count":
            len(available),
        "spearman":
            _spearman(
                projected,
                realised,
            ),
        "projected_mean":
            (
                round(
                    mean(projected),
                    2,
                )
                if projected
                else None
            ),
        "realised_mean":
            (
                round(
                    mean(realised),
                    2,
                )
                if realised
                else None
            ),
        "mean_error":
            (
                round(
                    mean(errors),
                    2,
                )
                if errors
                else None
            ),
        "mean_absolute_error":
            (
                round(
                    mean(
                        abs(error)
                        for error in errors
                    ),
                    2,
                )
                if errors
                else None
            ),
        "starter_projected_mean":
            (
                round(
                    mean(
                        starter_components
                    ),
                    2,
                )
                if starter_components
                else None
            ),
        "captain_projected_mean":
            (
                round(
                    mean(
                        captain_components
                    ),
                    2,
                )
                if captain_components
                else None
            ),
    }


def _fh_baseline_model_row(
    case,
):
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

    return {
        "kind":
            case["kind"],
        "projected_uplift":
            case.get(
                "projected_uplift"
            ),
        "realised_uplift":
            case["outcome"],
        "starter_projected_uplift":
            (
                float(
                    free_hit[
                        "starter_projected_score"
                    ]
                )
                - float(
                    template[
                        "starter_projected_score"
                    ]
                )
                if (
                    free_hit.get(
                        "starter_projected_score"
                    ) is not None
                    and template.get(
                        "starter_projected_score"
                    ) is not None
                )
                else None
            ),
        "captain_projected_uplift":
            (
                float(
                    free_hit[
                        "captain_projection"
                    ]
                )
                - float(
                    template[
                        "captain_projection"
                    ]
                )
                if (
                    free_hit.get(
                        "captain_projection"
                    ) is not None
                    and template.get(
                        "captain_projection"
                    ) is not None
                )
                else None
            ),
    }


def _fh_sensitivity_model_for_case(
    case,
    key,
):
    models = (
        (
            case.get("detail")
            or {}
        ).get(
            "sensitivity_models",
            [],
        )
    )

    return next(
        (
            row
            for row in models
            if row.get(
                "key"
            ) == key
        ),
        None,
    )


def _fh_sensitivity_summaries(
    cases,
):
    definitions = [
        {
            "key": "baseline",
            "label": "Current proxy",
            "note": (
                "Existing pre-deadline FH proxy."
            ),
        },
        {
            "key": "captain_pool_50",
            "label": "Top-50 ownership captain rescore",
            "note": (
                "Rescores selected squads with a broad, "
                "ownership-based captain pool."
            ),
        },
        {
            "key": "history_floor",
            "label": "Minimum history (5 season/2 recent)",
            "note": (
                "FH candidates require five season and two "
                "recent appearances."
            ),
        },
        {
            "key": "regressed_form",
            "label": "Regressed small samples (toward 2 PPG)",
            "note": (
                "Small-sample PPG is regressed toward two "
                "points per appearance."
            ),
        },
    ]
    summaries = []

    for definition in definitions:
        rows = []
        paired_baseline_rows = []

        for case in cases:
            if definition["key"] == "baseline":
                baseline_row = (
                    _fh_baseline_model_row(
                        case
                    )
                )
                rows.append(
                    baseline_row
                )
                paired_baseline_rows.append(
                    baseline_row
                )
                continue

            model = (
                _fh_sensitivity_model_for_case(
                    case,
                    definition[
                        "key"
                    ],
                )
            )

            if (
                model is None
                or not model.get(
                    "available",
                    False,
                )
            ):
                continue

            rows.append({
                **model,
                "kind":
                    case["kind"],
            })
            paired_baseline_rows.append(
                _fh_baseline_model_row(
                    case
                )
            )

        summaries.append({
            **definition,
            "overall":
                _fh_model_metrics(
                    rows
                ),
            "blank_only":
                _fh_model_metrics(
                    [
                        row
                        for row in rows
                        if row["kind"]
                        == "blank"
                    ]
                ),
            "blank_double":
                _fh_model_metrics(
                    [
                        row
                        for row in rows
                        if row["kind"]
                        == "blank_double"
                    ]
                ),
            "paired_baseline": {
                "overall":
                    _fh_model_metrics(
                        paired_baseline_rows
                    ),
                "blank_only":
                    _fh_model_metrics(
                        [
                            row
                            for row
                            in paired_baseline_rows
                            if row["kind"]
                            == "blank"
                        ]
                    ),
                "blank_double":
                    _fh_model_metrics(
                        [
                            row
                            for row
                            in paired_baseline_rows
                            if row["kind"]
                            == "blank_double"
                        ]
                    ),
            },
        })

    return summaries


def _empirical_percentile(
    value,
    reference,
):
    if not reference:
        return None

    lower = sum(
        1
        for item in reference
        if item < value
    )
    equal = sum(
        1
        for item in reference
        if item == value
    )

    return (
        lower
        + 0.5 * equal
    ) / len(reference)


def _fh_rank_comparison(rows):
    outcomes = [row["realised_uplift"] for row in rows]
    signal = _spearman([row["signal_score"] for row in rows], outcomes)
    blend = _spearman([row["combined_score"] for row in rows], outcomes)
    return {
        "case_count": len(rows),
        "signal_spearman": signal,
        "combined_spearman": blend,
        "blend_delta": (
            round(blend - signal, 3)
            if signal is not None and blend is not None else None
        ),
    }


def _fh_top_week(rows, score_key):
    """Average outcomes across tied first choices; never break ties with outcomes."""
    if not rows:
        return None
    best_score = max(row[score_key] for row in rows)
    selected = [row for row in rows if row[score_key] == best_score]
    realised = sum(row["realised_uplift"] for row in selected) / len(selected)
    return {
        "gameweeks": sorted(row["gameweek"] for row in selected),
        "realised_uplift": round(realised, 3),
        "regret": round(max(row["realised_uplift"] for row in rows) - realised, 3),
    }


def _fh_blank_rank_stability(scored):
    """Fixed research gate, not production calibration or a significance test.

    Season deletions summarise existing out-of-fold predictions; they do not
    refit percentiles. Each season has equal weight in the top-week comparison.
    """
    seasons = sorted({row["season"] for row in scored})
    by_season = []
    deletions = []
    for season in seasons:
        held = [row for row in scored if row["season"] == season]
        by_season.append({
            "season": season,
            **_fh_rank_comparison(held),
            "fixture_top_week": _fh_top_week(held, "signal_score"),
            "blend_top_week": _fh_top_week(held, "combined_score"),
        })
        deletions.append({
            "omitted_season": season,
            **_fh_rank_comparison([
                row for row in scored if row["season"] != season
            ]),
        })
    overall = _fh_rank_comparison(scored)
    informative = [row for row in by_season if row["blend_delta"] is not None]
    improved = sum(row["blend_delta"] > 0 for row in informative)
    signal_regret = (
        sum(row["fixture_top_week"]["regret"] for row in by_season) / len(seasons)
        if seasons else None
    )
    blend_regret = (
        sum(row["blend_top_week"]["regret"] for row in by_season) / len(seasons)
        if seasons else None
    )
    checks = [
        {"label": "At least three informative held-out seasons",
         "passed": len(informative) >= 3},
        {"label": "Blend improves pooled out-of-fold Spearman",
         "passed": overall["blend_delta"] is not None and overall["blend_delta"] > 0},
        {"label": "Blend improves a majority of informative seasons",
         "passed": improved > len(informative) / 2},
        {"label": "No negative delta after any season deletion",
         "passed": bool(deletions) and all(
             row["blend_delta"] is not None and row["blend_delta"] >= 0
             for row in deletions
         )},
        {"label": "Blend does not increase mean top-week regret",
         "passed": signal_regret is not None and blend_regret <= signal_regret},
    ]
    accepted = all(check["passed"] for check in checks)
    return {
        "archetype": "blank_only",
        "status": "RESEARCH CANDIDATE" if accepted else "HOLD",
        "preferred_research_model": "equal_rank_blend" if accepted else "fixture_only",
        "production_status": "Uncalibrated: archived deadline inputs still require audit.",
        "overall": overall,
        "informative_seasons": len(informative),
        "improved_seasons": improved,
        "fixture_mean_top_week_regret": round(signal_regret, 3) if seasons else None,
        "blend_mean_top_week_regret": round(blend_regret, 3) if seasons else None,
        "seasons": by_season,
        "season_deletions": deletions,
        "checks": checks,
    }


def _fh_blank_only_loso_validation(
    cases,
):
    rows = []

    for case in cases:
        if case["kind"] != "blank":
            continue

        model = (
            _fh_sensitivity_model_for_case(
                case,
                "regressed_form",
            )
        )

        if (
            model is None
            or not model.get(
                "available",
                False,
            )
        ):
            continue

        rows.append({
            "season":
                case["season"],
            "gameweek":
                case["gameweek"],
            "signal":
                float(
                    case["signal"]
                ),
            "projected_uplift":
                float(
                    model[
                        "projected_uplift"
                    ]
                ),
            "realised_uplift":
                float(
                    model[
                        "realised_uplift"
                    ]
                ),
        })

    scored = []
    season_summaries = []

    for season in sorted({
        row["season"]
        for row in rows
    }):
        training = [
            row
            for row in rows
            if row["season"]
            != season
        ]
        held_out = [
            row
            for row in rows
            if row["season"]
            == season
        ]
        training_signals = [
            row["signal"]
            for row in training
        ]
        training_projections = [
            row[
                "projected_uplift"
            ]
            for row in training
        ]
        held_scores = []

        for row in held_out:
            signal_score = (
                _empirical_percentile(
                    row["signal"],
                    training_signals,
                )
            )
            projection_score = (
                _empirical_percentile(
                    row[
                        "projected_uplift"
                    ],
                    training_projections,
                )
            )

            if (
                signal_score is None
                or projection_score
                is None
            ):
                continue

            scored_row = {
                **row,
                "signal_score":
                    signal_score,
                "projection_score":
                    projection_score,
                "combined_score":
                    (
                        signal_score
                        + projection_score
                    ) / 2,
            }
            scored.append(
                scored_row
            )
            held_scores.append(
                scored_row
            )

        outcomes = [
            row[
                "realised_uplift"
            ]
            for row in held_scores
        ]
        season_summaries.append({
            "season":
                season,
            "case_count":
                len(held_scores),
            "signal_spearman":
                _spearman(
                    [
                        row[
                            "signal_score"
                        ]
                        for row
                        in held_scores
                    ],
                    outcomes,
                ),
            "projection_spearman":
                _spearman(
                    [
                        row[
                            "projection_score"
                        ]
                        for row
                        in held_scores
                    ],
                    outcomes,
                ),
            "combined_spearman":
                _spearman(
                    [
                        row[
                            "combined_score"
                        ]
                        for row
                        in held_scores
                    ],
                    outcomes,
                ),
        })

    outcomes = [
        row[
            "realised_uplift"
        ]
        for row in scored
    ]

    return {
        "case_count":
            len(scored),
        "signal_spearman":
            _spearman(
                [
                    row[
                        "signal_score"
                    ]
                    for row in scored
                ],
                outcomes,
            ),
        "projection_spearman":
            _spearman(
                [
                    row[
                        "projection_score"
                    ]
                    for row in scored
                ],
                outcomes,
            ),
        "combined_spearman":
            _spearman(
                [
                    row[
                        "combined_score"
                    ]
                    for row in scored
                ],
                outcomes,
            ),
        "seasons":
            season_summaries,
        "ranking_stability": _fh_blank_rank_stability(scored),
        "mixed_blank_double_status":
            (
                "Uncalibrated: only eight historical cases; "
                "no combined model fitted."
            ),
    }


def _quantile(
    values,
    fraction,
):
    ordered = sorted(
        float(value)
        for value in values
    )

    if not ordered:
        return None

    index = int(
        round(
            (len(ordered) - 1)
            * float(fraction)
        )
    )

    return ordered[index]


def _fh_calibration_pool_rows(
    cases,
):
    rows = []

    for case in cases:
        if case["kind"] != "blank":
            continue

        player_pool = (
            (
                case.get("detail")
                or {}
            ).get(
                "player_pool",
                {},
            )
        )

        for player in player_pool.get(
            "calibration_players",
            [],
        ):
            rows.append({
                **player,
                "season":
                    case["season"],
                "gameweek":
                    case["gameweek"],
            })

    return rows


def _fh_player_projection_metrics(
    rows,
):
    active = [
        row
        for row in rows
        if int(
            row.get(
                "fixture_rows",
                0,
            )
            or 0
        ) > 0
    ]

    if not active:
        return {
            "player_count": 0,
            "spearman": None,
            "projected_mean": None,
            "actual_mean": None,
            "mean_error": None,
            "mean_absolute_error": None,
        }

    projected = [
        float(
            row.get(
                "regressed_projection",
                0.0,
            )
            or 0.0
        )
        for row in active
    ]
    actual = [
        float(
            row.get(
                "total_points",
                0.0,
            )
            or 0.0
        )
        for row in active
    ]
    errors = [
        predicted - realised
        for predicted, realised
        in zip(
            projected,
            actual,
        )
    ]

    return {
        "player_count":
            len(active),
        "spearman":
            _spearman(
                projected,
                actual,
            ),
        "projected_mean":
            round(
                mean(projected),
                2,
            ),
        "actual_mean":
            round(
                mean(actual),
                2,
            ),
        "mean_error":
            round(
                mean(errors),
                2,
            ),
        "mean_absolute_error":
            round(
                mean(
                    abs(error)
                    for error in errors
                ),
                2,
            ),
    }


def _fh_player_projection_diagnostics(
    cases,
):
    rows = _fh_calibration_pool_rows(
        cases
    )
    active = [
        row
        for row in rows
        if int(
            row.get(
                "fixture_rows",
                0,
            )
            or 0
        ) > 0
    ]
    role_definitions = (
        (
            "free_hit_xi",
            "Selected for FH XI",
            lambda row: row.get(
                "free_hit_starter",
                False,
            ),
        ),
        (
            "template_xi",
            "Selected for template XI",
            lambda row: row.get(
                "template_starter",
                False,
            ),
        ),
        (
            "rejected",
            "Active but rejected by both XIs",
            lambda row: not row.get(
                "free_hit_starter",
                False,
            )
            and not row.get(
                "template_starter",
                False,
            ),
        ),
    )
    sample_definitions = (
        (
            "limited",
            "Limited history",
            lambda row: (
                int(
                    row.get(
                        "season_appearances",
                        0,
                    )
                    or 0
                )
                < SMALL_SAMPLE_SEASON_APPEARANCES
                or int(
                    row.get(
                        "recent_appearances",
                        0,
                    )
                    or 0
                )
                < SMALL_SAMPLE_RECENT_APPEARANCES
            ),
        ),
        (
            "established",
            "Established history",
            lambda row: (
                int(
                    row.get(
                        "season_appearances",
                        0,
                    )
                    or 0
                )
                >= SMALL_SAMPLE_SEASON_APPEARANCES
                and int(
                    row.get(
                        "recent_appearances",
                        0,
                    )
                    or 0
                )
                >= SMALL_SAMPLE_RECENT_APPEARANCES
            ),
        ),
    )
    band_definitions = (
        ("under_4", "Under 4", 0.0, 4.0),
        ("4_to_6", "4 to under 6", 4.0, 6.0),
        ("6_to_8", "6 to under 8", 6.0, 8.0),
        ("8_plus", "8 or more", 8.0, None),
    )

    return {
        "overall":
            _fh_player_projection_metrics(
                active
            ),
        "by_role": [
            {
                "key": key,
                "label": label,
                **_fh_player_projection_metrics(
                    [
                        row
                        for row in active
                        if predicate(row)
                    ]
                ),
            }
            for key, label, predicate
            in role_definitions
        ],
        "by_position": [
            {
                "key": position,
                "label": position,
                **_fh_player_projection_metrics(
                    [
                        row
                        for row in active
                        if row.get(
                            "position"
                        ) == position
                    ]
                ),
            }
            for position in POSITION_LIMITS
        ],
        "by_sample": [
            {
                "key": key,
                "label": label,
                **_fh_player_projection_metrics(
                    [
                        row
                        for row in active
                        if predicate(row)
                    ]
                ),
            }
            for key, label, predicate
            in sample_definitions
        ],
        "by_projection_band": [
            {
                "key": key,
                "label": label,
                **_fh_player_projection_metrics(
                    [
                        row
                        for row in active
                        if (
                            float(
                                row.get(
                                    "regressed_projection",
                                    0.0,
                                )
                                or 0.0
                            )
                            >= lower
                            and (
                                upper is None
                                or float(
                                    row.get(
                                        "regressed_projection",
                                        0.0,
                                    )
                                    or 0.0
                                ) < upper
                            )
                        )
                    ]
                ),
            }
            for key, label, lower, upper
            in band_definitions
        ],
    }


def _fh_position_calibration_stats(
    rows,
):
    active = [
        row
        for row in rows
        if int(
            row.get(
                "fixture_rows",
                0,
            )
            or 0
        ) > 0
    ]
    all_points = [
        float(
            row.get(
                "total_points",
                0.0,
            )
            or 0.0
        )
        for row in active
    ]
    fallback_prior = (
        mean(all_points)
        if all_points
        else FORM_REGRESSION_POINTS_PER_APPEARANCE
    )
    fallback_cap = (
        _quantile(
            all_points,
            CALIBRATION_PROJECTION_CAP_QUANTILE,
        )
        if all_points
        else fallback_prior
    )
    result = {}

    for position in POSITION_LIMITS:
        points = [
            float(
                row.get(
                    "total_points",
                    0.0,
                )
                or 0.0
            )
            for row in active
            if row.get(
                "position"
            ) == position
        ]
        result[position] = {
            "prior":
                mean(points)
                if points
                else fallback_prior,
            "cap":
                _quantile(
                    points,
                    CALIBRATION_PROJECTION_CAP_QUANTILE,
                )
                if points
                else fallback_cap,
            "player_count":
                len(points),
        }

    return result


def _weighted_isotonic_values(
    values,
    weights,
):
    blocks = []

    for index, (value, weight) in enumerate(
        zip(values, weights)
    ):
        block = {
            "start": index,
            "end": index,
            "weight": float(weight),
            "weighted_value":
                float(value)
                * float(weight),
        }
        blocks.append(block)

        while len(blocks) >= 2:
            previous = blocks[-2]
            current = blocks[-1]
            previous_mean = (
                previous[
                    "weighted_value"
                ]
                / previous["weight"]
            )
            current_mean = (
                current[
                    "weighted_value"
                ]
                / current["weight"]
            )

            if previous_mean <= current_mean:
                break

            blocks[-2:] = [{
                "start":
                    previous["start"],
                "end":
                    current["end"],
                "weight":
                    previous["weight"]
                    + current["weight"],
                "weighted_value":
                    previous[
                        "weighted_value"
                    ]
                    + current[
                        "weighted_value"
                    ],
            }]

    result = [
        0.0
        for _value in values
    ]

    for block in blocks:
        fitted = (
            block["weighted_value"]
            / block["weight"]
        )

        for index in range(
            block["start"],
            block["end"] + 1,
        ):
            result[index] = fitted

    return result


def _fh_soft_monotonic_curve(
    rows,
):
    active = [
        row
        for row in rows
        if int(
            row.get(
                "fixture_rows",
                0,
            )
            or 0
        ) > 0
    ]
    points = [{
        "projection": 0.0,
        "actual": 0.0,
        "player_count": 1,
    }]

    for lower, upper in (
        CALIBRATION_PROJECTION_BANDS
    ):
        band = [
            row
            for row in active
            if (
                float(
                    row.get(
                        "regressed_projection",
                        0.0,
                    )
                    or 0.0
                )
                >= lower
                and (
                    upper is None
                    or float(
                        row.get(
                            "regressed_projection",
                            0.0,
                        )
                        or 0.0
                    ) < upper
                )
            )
        ]

        if not band:
            continue

        projection = mean(
            float(
                row.get(
                    "regressed_projection",
                    0.0,
                )
                or 0.0
            )
            for row in band
        )

        if projection <= points[-1][
            "projection"
        ]:
            continue

        points.append({
            "projection":
                projection,
            "actual":
                mean(
                    float(
                        row.get(
                            "total_points",
                            0.0,
                        )
                        or 0.0
                    )
                    for row in band
                ),
            "player_count":
                len(band),
        })

    fitted = _weighted_isotonic_values(
        [
            point["actual"]
            for point in points
        ],
        [
            point["player_count"]
            for point in points
        ],
    )

    return [
        {
            **point,
            "calibrated":
                fitted[index],
        }
        for index, point
        in enumerate(points)
    ]


def _fh_soft_monotonic_projection(
    projection,
    curve,
):
    projection = max(
        0.0,
        float(projection),
    )

    if not curve:
        return projection

    if projection <= curve[0][
        "projection"
    ]:
        mapped = float(
            curve[0]["calibrated"]
        )
    elif projection >= curve[-1][
        "projection"
    ]:
        mapped = float(
            curve[-1]["calibrated"]
        )
    else:
        mapped = projection

        for left, right in zip(
            curve,
            curve[1:],
        ):
            if (
                left["projection"]
                <= projection
                <= right["projection"]
            ):
                width = (
                    right["projection"]
                    - left["projection"]
                )
                share = (
                    projection
                    - left["projection"]
                ) / width
                mapped = (
                    float(
                        left["calibrated"]
                    )
                    + share
                    * (
                        float(
                            right[
                                "calibrated"
                            ]
                        )
                        - float(
                            left[
                                "calibrated"
                            ]
                        )
                    )
                )
                break

    return (
        (
            1.0
            - SOFT_MONOTONIC_CALIBRATION_BLEND
        )
        * projection
        + SOFT_MONOTONIC_CALIBRATION_BLEND
        * mapped
    )


def _fh_calibrated_players(
    players,
    position_stats,
    variant,
    calibration_curve=None,
):
    result = []

    for player in players:
        fixture_rows = int(
            player.get(
                "fixture_rows",
                0,
            )
            or 0
        )
        base = float(
            player.get(
                "regressed_projection",
                player.get(
                    "projection",
                    0.0,
                ),
            )
            or 0.0
        )
        stats = position_stats.get(
            player.get("position"),
            {
                "prior":
                    FORM_REGRESSION_POINTS_PER_APPEARANCE,
                "cap":
                    base,
            },
        )
        prior = float(
            stats["prior"]
        ) * fixture_rows

        if fixture_rows <= 0:
            calibrated = 0.0
        elif variant == "regressed_form":
            calibrated = base
        elif variant == "position_regression":
            calibrated = (
                0.5 * base
                + 0.5 * prior
            )
        elif variant == "soft_monotonic_band":
            calibrated = (
                _fh_soft_monotonic_projection(
                    base,
                    calibration_curve,
                )
            )
        elif variant == "hybrid_band_position":
            soft_monotonic = (
                _fh_soft_monotonic_projection(
                    base,
                    calibration_curve,
                )
            )
            position_regressed = (
                0.5 * base
                + 0.5 * prior
            )
            calibrated = (
                0.5 * soft_monotonic
                + 0.5 * position_regressed
            )
        else:
            season_reliability = min(
                1.0,
                int(
                    player.get(
                        "season_appearances",
                        0,
                    )
                    or 0
                )
                / CALIBRATION_SEASON_APPEARANCES,
            )
            recent_reliability = min(
                1.0,
                int(
                    player.get(
                        "recent_minutes",
                        0,
                    )
                    or 0
                )
                / CALIBRATION_RECENT_MINUTES,
            )
            projection_weight = (
                0.25
                + 0.5
                * season_reliability
                * recent_reliability
            )
            calibrated = (
                projection_weight
                * base
                + (
                    1.0
                    - projection_weight
                )
                * prior
            )

            if variant == "history_position_cap":
                calibrated = min(
                    calibrated,
                    float(
                        stats["cap"]
                    ) * fixture_rows,
                )

        result.append({
            **player,
            "projection":
                round(
                    max(
                        0.0,
                        calibrated,
                    ),
                    4,
                ),
        })

    return result


def _fh_calibration_case_result(
    case,
    position_stats,
    variant,
    calibration_curve=None,
):
    players = (
        (
            (
                case.get("detail")
                or {}
            ).get(
                "player_pool",
                {},
            )
        ).get(
            "calibration_players",
            [],
        )
    )
    calibrated = _fh_calibrated_players(
        players,
        position_stats,
        variant,
        calibration_curve=(
            calibration_curve
        ),
    )
    free_hit = _solve_projected_free_hit(
        calibrated,
        captain_ownership_tiebreak=(
            variant in {
                "soft_monotonic_band",
                "hybrid_band_position",
            }
        ),
    )
    template_squad = [
        player
        for player in calibrated
        if player.get(
            "template_squad",
            False,
        )
    ]
    template = (
        _score_predeadline_lineup(
            template_squad
        )
        if len(template_squad) == 15
        else None
    )

    if (
        free_hit is None
        or template is None
    ):
        return None

    captain_player = next(
        (
            player
            for player in calibrated
            if player["player_name"]
            == free_hit["captain"]
        ),
        None,
    )

    return {
        "season":
            case["season"],
        "gameweek":
            case["gameweek"],
        "signal":
            float(case["signal"]),
        "projected_uplift":
            round(
                free_hit[
                    "projected_score"
                ]
                - template[
                    "projected_score"
                ],
                2,
            ),
        "realised_uplift":
            float(
                free_hit["score"]
                - template["score"]
            ),
        "starter_projected_uplift":
            round(
                free_hit[
                    "starter_projected_score"
                ]
                - template[
                    "starter_projected_score"
                ],
                2,
            ),
        "captain_projected_uplift":
            round(
                free_hit[
                    "captain_projection"
                ]
                - template[
                    "captain_projection"
                ],
                2,
            ),
        "captain":
            free_hit["captain"],
        "captain_position":
            (
                captain_player.get(
                    "position"
                )
                if captain_player
                else None
            ),
        "maximum_starter_projection":
            round(
                max(
                    float(
                        player[
                            "projection"
                        ]
                    )
                    for player in free_hit[
                        "starters"
                    ]
                ),
                2,
            ),
    }


def _fh_player_calibration_validation(
    cases,
):
    blank_cases = [
        case
        for case in cases
        if case["kind"] == "blank"
        and (
            (
                case.get("detail")
                or {}
            ).get(
                "player_pool",
                {},
            ).get(
                "calibration_players"
            )
        )
    ]
    pool_rows = _fh_calibration_pool_rows(
        blank_cases
    )
    variants = (
        (
            "regressed_form",
            "Regressed-form baseline",
        ),
        (
            "position_regression",
            "50% regression to position prior",
        ),
        (
            "history_position",
            "History-weighted position regression",
        ),
        (
            "history_position_cap",
            "History-weighted regression + position cap",
        ),
        (
            "soft_monotonic_band",
            "Soft monotonic projection-band correction",
        ),
        (
            "hybrid_band_position",
            "50/25/25 raw/band/position hybrid",
        ),
    )
    model_rows = {
        key: []
        for key, _label in variants
    }

    for season in sorted({
        case["season"]
        for case in blank_cases
    }):
        training_rows = [
            row
            for row in pool_rows
            if row["season"]
            != season
        ]
        position_stats = (
            _fh_position_calibration_stats(
                training_rows
            )
        )
        calibration_curve = (
            _fh_soft_monotonic_curve(
                training_rows
            )
        )

        for case in blank_cases:
            if case["season"] != season:
                continue

            for key, _label in variants:
                row = (
                    _fh_calibration_case_result(
                        case,
                        position_stats,
                        key,
                        calibration_curve=(
                            calibration_curve
                        ),
                    )
                )

                if row is not None:
                    model_rows[key].append(
                        row
                    )

    summaries = []

    for key, label in variants:
        rows = model_rows[key]
        season_summaries = []

        for season in sorted({
            row["season"]
            for row in rows
        }):
            season_rows = [
                row
                for row in rows
                if row["season"]
                == season
            ]
            season_metrics = (
                _fh_model_metrics(
                    season_rows
                )
            )
            season_summaries.append({
                "season": season,
                **season_metrics,
            })

        metrics = _fh_model_metrics(
            rows
        )
        summaries.append({
            "key": key,
            "label": label,
            **metrics,
            "signal_spearman":
                _spearman(
                    [
                        row["signal"]
                        for row in rows
                    ],
                    [
                        row[
                            "realised_uplift"
                        ]
                        for row in rows
                    ],
                ),
            "implausible_captain_count":
                sum(
                    1
                    for row in rows
                    if row.get(
                        "captain_position"
                    ) in {
                        "GKP",
                        "DEF",
                    }
                ),
            "maximum_starter_projection":
                (
                    max(
                        row[
                            "maximum_starter_projection"
                        ]
                        for row in rows
                    )
                    if rows
                    else None
                ),
            "seasons":
                season_summaries,
        })

    summaries_by_key = {
        row["key"]: row
        for row in summaries
    }
    candidate = summaries_by_key.get(
        "hybrid_band_position",
        {},
    )
    baseline = summaries_by_key.get(
        "regressed_form",
        {},
    )
    calibration_benchmark = (
        summaries_by_key.get(
            "position_regression",
            {},
        )
    )
    acceptance_checks = [
        {
            "label": (
                "Projection Spearman exceeds "
                "regressed-form baseline"
            ),
            "candidate":
                candidate.get("spearman"),
            "benchmark":
                baseline.get("spearman"),
            "passed": (
                candidate.get("spearman")
                is not None
                and baseline.get("spearman")
                is not None
                and candidate["spearman"]
                > baseline["spearman"]
            ),
        },
        {
            "label": (
                "MAE does not exceed 50% "
                "position-regression benchmark"
            ),
            "candidate":
                candidate.get(
                    "mean_absolute_error"
                ),
            "benchmark":
                calibration_benchmark.get(
                    "mean_absolute_error"
                ),
            "passed": (
                candidate.get(
                    "mean_absolute_error"
                ) is not None
                and calibration_benchmark.get(
                    "mean_absolute_error"
                ) is not None
                and candidate[
                    "mean_absolute_error"
                ]
                <= calibration_benchmark[
                    "mean_absolute_error"
                ]
            ),
        },
        {
            "label": (
                "GK/DEF captain count does not "
                "exceed regressed-form baseline"
            ),
            "candidate":
                candidate.get(
                    "implausible_captain_count"
                ),
            "benchmark":
                baseline.get(
                    "implausible_captain_count"
                ),
            "passed": (
                candidate.get(
                    "implausible_captain_count"
                ) is not None
                and baseline.get(
                    "implausible_captain_count"
                ) is not None
                and candidate[
                    "implausible_captain_count"
                ]
                <= baseline[
                    "implausible_captain_count"
                ]
            ),
        },
        {
            "label": (
                "Realised uplift does not fall below "
                "regressed-form baseline"
            ),
            "candidate":
                candidate.get("realised_mean"),
            "benchmark":
                baseline.get("realised_mean"),
            "passed": (
                candidate.get("realised_mean")
                is not None
                and baseline.get("realised_mean")
                is not None
                and candidate["realised_mean"]
                >= baseline["realised_mean"]
            ),
        },
    ]

    return {
        "case_count":
            len(blank_cases),
        "training_policy": (
            "Each held-out season is calibrated only from "
            "player outcomes in the other seasons."
        ),
        "player_diagnostics":
            _fh_player_projection_diagnostics(
                blank_cases
            ),
        "models":
            summaries,
        "candidate_acceptance": {
            "candidate_key":
                "hybrid_band_position",
            "passed":
                all(
                    row["passed"]
                    for row
                    in acceptance_checks
                ),
            "checks":
                acceptance_checks,
        },
        "mixed_blank_double_status": (
            "Uncalibrated: mixed blank/double weeks remain "
            "outside player-level model fitting."
        ),
    }


def _fh_projection_error_diagnostics(
    cases,
    limit=5,
):
    rows = []

    for case in cases:
        projected = case.get(
            "projected_uplift"
        )

        if projected is None:
            continue

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
        starter = None
        captain = None

        if (
            free_hit.get(
                "starter_projected_score"
            ) is not None
            and template.get(
                "starter_projected_score"
            ) is not None
        ):
            starter = round(
                float(
                    free_hit[
                        "starter_projected_score"
                    ]
                )
                - float(
                    template[
                        "starter_projected_score"
                    ]
                ),
                2,
            )

        if (
            free_hit.get(
                "captain_projection"
            ) is not None
            and template.get(
                "captain_projection"
            ) is not None
        ):
            captain = round(
                float(
                    free_hit[
                        "captain_projection"
                    ]
                )
                - float(
                    template[
                        "captain_projection"
                    ]
                ),
                2,
            )

        rows.append({
            "season":
                case["season"],
            "gameweek":
                case["gameweek"],
            "kind":
                case["kind"],
            "projected_uplift":
                float(projected),
            "realised_uplift":
                float(
                    case["outcome"]
                ),
            "error":
                round(
                    float(projected)
                    - float(
                        case[
                            "outcome"
                        ]
                    ),
                    2,
                ),
            "starter_projected_uplift":
                starter,
            "captain_projected_uplift":
                captain,
            "blank_team_count":
                case.get(
                    "blank_team_count"
                ),
            "double_team_count":
                case.get(
                    "double_team_count"
                ),
            "active_team_count":
                case.get(
                    "active_team_count"
                ),
            "scheduled_fixture_count":
                case.get(
                    "scheduled_fixture_count"
                ),
            "template_score":
                template.get("score"),
            "free_hit_score":
                free_hit.get("score"),
            "template_projection":
                template.get(
                    "projected_score"
                ),
            "free_hit_projection":
                free_hit.get(
                    "projected_score"
                ),
            "template_captain":
                template.get("captain"),
            "free_hit_captain":
                free_hit.get("captain"),
            "template_xi":
                detail.get("template_xi"),
            "free_hit_xi":
                detail.get("free_hit_xi"),
            "captain_sanity":
                detail.get(
                    "captain_sanity"
                ),
        })

    return {
        "highest_projected":
            sorted(
                rows,
                key=lambda row: (
                    -row[
                        "projected_uplift"
                    ],
                    row["season"],
                    row["gameweek"],
                ),
            )[:int(limit)],
        "largest_overprediction":
            sorted(
                rows,
                key=lambda row: (
                    -row["error"],
                    row["season"],
                    row["gameweek"],
                ),
            )[:int(limit)],
        "largest_underprediction":
            sorted(
                rows,
                key=lambda row: (
                    row["error"],
                    row["season"],
                    row["gameweek"],
                ),
            )[:int(limit)],
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


def _shape_breakdown(cases):
    groups = {}

    for row in cases:
        kind = str(
            row.get(
                "kind",
                "unknown",
            )
        )
        groups.setdefault(
            kind,
            [],
        ).append(
            row
        )

    result = []

    for kind, rows in sorted(
        groups.items()
    ):
        signals = [
            row["signal"]
            for row in rows
        ]
        outcomes = [
            row["outcome"]
            for row in rows
        ]

        result.append({
            "kind":
                kind,
            "case_count":
                len(rows),
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
            "signal_mean":
                (
                    round(
                        mean(signals),
                        2,
                    )
                    if signals
                    else None
                ),
            "outcome_min":
                (
                    round(
                        min(outcomes),
                        2,
                    )
                    if outcomes
                    else None
                ),
            "outcome_max":
                (
                    round(
                        max(outcomes),
                        2,
                    )
                    if outcomes
                    else None
                ),
        })

    return result


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
                    "blank_team_count":
                        feature.get(
                            "blank_team_count"
                        ),
                    "double_team_count":
                        feature.get(
                            "double_team_count"
                        ),
                    "active_team_count":
                        feature.get(
                            "active_team_count"
                        ),
                    "scheduled_fixture_count":
                        feature.get(
                            "scheduled_fixture_count"
                        ),
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
            "sensitivity_models":
                (
                    _fh_sensitivity_summaries(
                        cases
                    )
                    if chip == "FH"
                    else []
                ),
            "projection_error_diagnostics":
                (
                    _fh_projection_error_diagnostics(
                        cases
                    )
                    if chip == "FH"
                    else None
                ),
            "blank_only_loso_validation":
                (
                    _fh_blank_only_loso_validation(
                        cases
                    )
                    if chip == "FH"
                    else None
                ),
            "player_calibration_validation":
                (
                    _fh_player_calibration_validation(
                        cases
                    )
                    if chip == "FH"
                    else None
                ),
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
            "shape_breakdown":
                _shape_breakdown(
                    cases
                ),
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
                "using prior-Gameweek ownership/form proxies and "
                "retrospective fixture inputs, then scored with actual points; "
                "BB and TC remain outcome ceilings. The source audit "
                "confirmed a post-deadline fixture reassignment and "
                "historical FDR/team-strength revisions. See "
                "docs/historical_input_audit.md. These inputs are not "
                "verified deadline snapshots. Do not use this "
                "report alone to retune live decision thresholds."
            ),
    }
