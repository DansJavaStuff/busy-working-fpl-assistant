from math import sqrt

from fpl_api import (
    get_bootstrap,
    get_fixtures,
)
from historical_chip_features import (
    historical_chip_features,
)
from history_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_database,
)


CHIP_SIGNAL_KEYS = {
    "FH": "free_hit_signal",
    "BB": "bench_boost_signal",
    "TC": "triple_captain_signal",
}

FEATURE_KEYS = (
    "blank_team_count",
    "double_team_count",
    "premium_blank_count",
    "premium_double_count",
    "mean_double_fixture_quality",
)


def _difficulty_quality(
    difficulty,
):
    if difficulty is None:
        return 0.0

    difficulty = max(
        1,
        min(
            5,
            int(difficulty),
        ),
    )

    return (
        5 - difficulty
    ) / 4


def _normalised_feature_vector(
    row,
):
    # Counts are normalised to the 20-team league.
    return (
        row.get(
            "blank_team_count",
            0,
        ) / 20.0,
        row.get(
            "double_team_count",
            0,
        ) / 20.0,
        row.get(
            "premium_blank_count",
            0,
        ) / 6.0,
        row.get(
            "premium_double_count",
            0,
        ) / 6.0,
        float(
            row.get(
                "mean_double_fixture_quality",
                0.0,
            )
            or 0.0
        ),
    )


def _similarity(
    current,
    historical,
):
    a = _normalised_feature_vector(
        current
    )
    b = _normalised_feature_vector(
        historical
    )

    distance = sqrt(
        sum(
            (x - y) ** 2
            for x, y in zip(a, b)
        )
        / len(a)
    )

    return round(
        max(
            0.0,
            1.0 - distance,
        )
        * 100,
        1,
    )


def imported_seasons(
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
            SELECT DISTINCT
                seasons.season_key,
                seasons.starts_year
            FROM seasons
            JOIN historical_imports
              ON historical_imports.season_id
                 = seasons.id
            ORDER BY seasons.starts_year
            """
        ).fetchall()

    return [
        row["season_key"]
        for row in rows
    ]


def historical_pattern_index(
    chip,
    seasons=None,
    db_path=DEFAULT_DB_PATH,
):
    chip = str(
        chip
    ).upper()

    signal_key = (
        CHIP_SIGNAL_KEYS.get(
            chip
        )
    )

    if signal_key is None:
        raise ValueError(
            "Historical analogues currently "
            "support FH, BB and TC."
        )

    if seasons is None:
        seasons = imported_seasons(
            db_path=db_path
        )

    rows = []

    for season_key in seasons:
        for row in historical_chip_features(
            season_key,
            db_path=db_path,
        ):
            if row[signal_key] <= 0:
                continue

            rows.append(
                row
            )

    return sorted(
        rows,
        key=lambda row: (
            -row[signal_key],
            row["season"],
            row["gameweek"],
        ),
    )


def current_gameweek_features(
    gameweek,
    bootstrap=None,
    fixtures=None,
):
    bootstrap = (
        bootstrap
        if bootstrap is not None
        else get_bootstrap()
    )
    fixtures = (
        fixtures
        if fixtures is not None
        else get_fixtures()
    )

    teams = bootstrap.get(
        "teams",
        []
    )

    strength_by_id = {
        int(team["id"]):
            int(
                team.get(
                    "strength",
                    0,
                )
                or 0
            )
        for team in teams
        if team.get("id") is not None
    }

    ranked = sorted(
        strength_by_id,
        key=lambda team_id: (
            -strength_by_id[
                team_id
            ],
            team_id,
        ),
    )

    premium_team_ids = set(
        ranked[:6]
    )

    team_fixtures = {
        team_id: []
        for team_id in strength_by_id
    }

    for fixture in fixtures:
        if fixture.get(
            "event"
        ) != gameweek:
            continue

        home_id = fixture.get(
            "team_h"
        )
        away_id = fixture.get(
            "team_a"
        )

        if home_id in team_fixtures:
            team_fixtures[
                home_id
            ].append(
                fixture.get(
                    "team_h_difficulty"
                )
            )

        if away_id in team_fixtures:
            team_fixtures[
                away_id
            ].append(
                fixture.get(
                    "team_a_difficulty"
                )
            )

    blank_ids = {
        team_id
        for team_id, rows
        in team_fixtures.items()
        if len(rows) == 0
    }
    double_ids = {
        team_id
        for team_id, rows
        in team_fixtures.items()
        if len(rows) >= 2
    }

    premium_blank_ids = (
        blank_ids
        & premium_team_ids
    )
    premium_double_ids = (
        double_ids
        & premium_team_ids
    )

    double_qualities = []

    for team_id in double_ids:
        double_qualities.extend(
            _difficulty_quality(
                difficulty
            )
            for difficulty
            in team_fixtures[
                team_id
            ]
        )

    mean_double_fixture_quality = (
        sum(
            double_qualities
        )
        / len(
            double_qualities
        )
        if double_qualities
        else 0.0
    )

    if (
        blank_ids
        and double_ids
    ):
        kind = "blank_double"
    elif blank_ids:
        kind = "blank"
    elif double_ids:
        kind = "double"
    else:
        kind = "normal"

    return {
        "gameweek":
            int(gameweek),
        "kind":
            kind,
        "blank_team_count":
            len(blank_ids),
        "double_team_count":
            len(double_ids),
        "premium_blank_count":
            len(
                premium_blank_ids
            ),
        "premium_double_count":
            len(
                premium_double_ids
            ),
        "mean_double_fixture_quality":
            round(
                mean_double_fixture_quality,
                3,
            ),
    }


def _structurally_applicable(
    chip,
    current_features,
    historical_features,
):
    chip = str(chip).upper()

    if chip == "FH":
        if current_features.get(
            "blank_team_count",
            0,
        ) <= 0:
            return False

        return (
            historical_features.get(
                "blank_team_count",
                0,
            ) > 0
        )

    if chip in {
        "BB",
        "TC",
    }:
        if current_features.get(
            "double_team_count",
            0,
        ) <= 0:
            return False

        return (
            historical_features.get(
                "double_team_count",
                0,
            ) > 0
        )

    return False


def closest_historical_analogues(
    chip,
    current_features,
    limit=5,
    seasons=None,
    db_path=DEFAULT_DB_PATH,
):
    chip = str(
        chip
    ).upper()

    signal_key = (
        CHIP_SIGNAL_KEYS.get(
            chip
        )
    )

    if signal_key is None:
        raise ValueError(
            "Historical analogues currently "
            "support FH, BB and TC."
        )

    index = historical_pattern_index(
        chip,
        seasons=seasons,
        db_path=db_path,
    )

    matches = []

    for row in index:
        if not _structurally_applicable(
            chip,
            current_features,
            row,
        ):
            continue
        match = dict(
            row
        )
        match["similarity"] = (
            _similarity(
                current_features,
                row,
            )
        )

        matches.append(
            match
        )

    return sorted(
        matches,
        key=lambda row: (
            -row["similarity"],
            -row[signal_key],
            row["season"],
            row["gameweek"],
        ),
    )[:int(limit)]


def current_historical_analogues(
    chip,
    gameweek,
    limit=5,
    bootstrap=None,
    fixtures=None,
    seasons=None,
    db_path=DEFAULT_DB_PATH,
):
    current = (
        current_gameweek_features(
            gameweek,
            bootstrap=bootstrap,
            fixtures=fixtures,
        )
    )

    analogues = (
        closest_historical_analogues(
            chip,
            current,
            limit=limit,
            seasons=seasons,
            db_path=db_path,
        )
    )

    return {
        "chip":
            str(chip).upper(),
        "gameweek":
            int(gameweek),
        "current":
            current,
        "analogues":
            analogues,
    }
