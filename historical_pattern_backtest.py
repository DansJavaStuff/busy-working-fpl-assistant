from statistics import median

from historical_analogues import (
    CHIP_SIGNAL_KEYS,
    closest_historical_analogues,
    imported_seasons,
)
from historical_chip_features import (
    historical_chip_features,
)
from history_store import DEFAULT_DB_PATH


DEFAULT_THRESHOLDS = (
    70.0,
    75.0,
    80.0,
    85.0,
    90.0,
)


def _percentile(values, fraction):
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        (len(ordered) - 1)
        * float(fraction)
    )
    lower = int(position)
    upper = min(
        len(ordered) - 1,
        lower + 1,
    )
    weight = position - lower

    return (
        ordered[lower]
        * (1.0 - weight)
        + ordered[upper]
        * weight
    )


def calibrate_historical_pattern_threshold(
    chip,
    seasons=None,
    thresholds=DEFAULT_THRESHOLDS,
    db_path=DEFAULT_DB_PATH,
):
    chip = str(chip).upper()

    signal_key = CHIP_SIGNAL_KEYS.get(
        chip
    )

    if signal_key is None:
        raise ValueError(
            "Pattern calibration currently "
            "supports FH, BB and TC."
        )

    if seasons is None:
        seasons = imported_seasons(
            db_path=db_path
        )

    seasons = list(seasons)
    cases = []

    for season in seasons:
        comparison_seasons = [
            other
            for other in seasons
            if other != season
        ]

        if not comparison_seasons:
            continue

        rows = historical_chip_features(
            season,
            db_path=db_path,
        )

        for row in rows:
            if float(
                row.get(
                    signal_key,
                    0.0,
                )
                or 0.0
            ) <= 0:
                continue

            analogues = (
                closest_historical_analogues(
                    chip,
                    row,
                    limit=1,
                    seasons=comparison_seasons,
                    db_path=db_path,
                )
            )

            best = (
                analogues[0]
                if analogues
                else None
            )

            cases.append({
                "season":
                    season,
                "gameweek":
                    row["gameweek"],
                "kind":
                    row["kind"],
                "signal":
                    row[signal_key],
                "matched":
                    best is not None,
                "similarity":
                    (
                        best[
                            "similarity"
                        ]
                        if best
                        else None
                    ),
                "analogue_season":
                    (
                        best["season"]
                        if best
                        else None
                    ),
                "analogue_gameweek":
                    (
                        best["gameweek"]
                        if best
                        else None
                    ),
                "analogue_signal":
                    (
                        best[
                            signal_key
                        ]
                        if best
                        else None
                    ),
            })

    similarities = [
        float(case["similarity"])
        for case in cases
        if case["similarity"]
        is not None
    ]

    threshold_rows = []

    for threshold in thresholds:
        threshold = float(
            threshold
        )
        passing = sum(
            similarity >= threshold
            for similarity in similarities
        )

        threshold_rows.append({
            "threshold":
                threshold,
            "passing":
                passing,
            "matched_cases":
                len(similarities),
            "coverage":
                (
                    round(
                        100
                        * passing
                        / len(similarities),
                        1,
                    )
                    if similarities
                    else None
                ),
        })

    return {
        "chip":
            chip,
        "seasons":
            seasons,
        "case_count":
            len(cases),
        "matched_count":
            len(similarities),
        "unmatched_count":
            len(cases)
            - len(similarities),
        "similarity_min":
            (
                round(
                    min(similarities),
                    1,
                )
                if similarities
                else None
            ),
        "similarity_p25":
            (
                round(
                    _percentile(
                        similarities,
                        0.25,
                    ),
                    1,
                )
                if similarities
                else None
            ),
        "similarity_median":
            (
                round(
                    median(
                        similarities
                    ),
                    1,
                )
                if similarities
                else None
            ),
        "similarity_p75":
            (
                round(
                    _percentile(
                        similarities,
                        0.75,
                    ),
                    1,
                )
                if similarities
                else None
            ),
        "similarity_max":
            (
                round(
                    max(similarities),
                    1,
                )
                if similarities
                else None
            ),
        "thresholds":
            threshold_rows,
        "cases":
            cases,
        "note":
            (
                "Leave-one-season-out fixture-pattern "
                "calibration only. This does not use "
                "realised player points or prove chip "
                "outcome quality."
            ),
    }


def calibrate_all_chip_patterns(
    seasons=None,
    thresholds=DEFAULT_THRESHOLDS,
    db_path=DEFAULT_DB_PATH,
):
    if seasons is None:
        seasons = imported_seasons(
            db_path=db_path
        )

    seasons = list(seasons)

    return {
        "seasons":
            seasons,
        "chips": [
            calibrate_historical_pattern_threshold(
                chip,
                seasons=seasons,
                thresholds=thresholds,
                db_path=db_path,
            )
            for chip in (
                "FH",
                "BB",
                "TC",
            )
        ],
        "note":
            (
                "Calibration with each target season "
                "excluded from its analogue pool."
            ),
    }
