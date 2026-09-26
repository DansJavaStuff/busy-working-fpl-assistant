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
from history_store import DEFAULT_DB_PATH


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
        outcome = (
            _solve_realised_squad(
                rows,
                "FH",
            )
        )
        baseline = (
            _solve_template_squad(
                rows
            )
        )

        if (
            outcome is None
            or baseline is None
        ):
            return None

        return {
            "metric":
                "fh_template_uplift_ceiling",
            "value":
                float(
                    outcome[
                        "score"
                    ]
                    - baseline[
                        "score"
                    ]
                ),
            "detail": {
                "free_hit":
                    outcome,
                "template":
                    {
                        key: value
                        for key, value
                        in baseline.items()
                        if key != "squad"
                    },
            },
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
                        )
                    )

                outcome = cache[key]

                if outcome is None:
                    continue

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
                        outcome[
                            "detail"
                        ],
                })

        signals = [
            row["signal"]
            for row in cases
        ]
        outcomes = [
            row["outcome"]
            for row in cases
        ]

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
                len(cases),
            "metric":
                (
                    cases[0][
                        "outcome_metric"
                    ]
                    if cases
                    else None
                ),
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
                "calibration. Outcome ceilings use actual FPL "
                "points, and the archived team-strength/FDR "
                "inputs have not yet been proven to be "
                "pre-deadline snapshots. Do not use this report "
                "alone to retune live decision thresholds."
            ),
    }
