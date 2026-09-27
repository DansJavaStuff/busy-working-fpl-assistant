from historical_analogues import (
    imported_seasons,
)
from historical_realised_backtest import (
    backtest_historical_chip_outcomes,
)


def _format_case(row):
    return (
        f"{row['season']} GW{row['gameweek']} "
        f"signal {row['signal']:.1f} · "
        f"outcome {row['outcome']:.1f}"
    )


def _format_lineup(
    lineup,
    captain,
):
    if not lineup:
        return "unavailable"

    return ", ".join(
        (
            f"{player['player']}"
            f"{' (C)' if player['player'] == captain else ''}"
            f" {player['points']}pts/"
            f"{player['fixture_rows']}fx/"
            f"{player['projection']:.1f}pred"
        )
        for player in lineup[
            "players"
        ]
    )


def main():
    seasons = imported_seasons()

    report = (
        backtest_historical_chip_outcomes(
            seasons
        )
    )

    print(
        "Historical realised chip-opportunity backtest"
    )
    print(
        "Seasons:",
        ", ".join(
            report["seasons"]
        ),
    )
    print()

    for chip in report["chips"]:
        print(
            f"{chip['chip']}: "
            f"{chip['case_count']} cases · "
            f"{chip['metric']}"
        )
        print(
            "  Spearman signal/outcome:",
            chip["spearman"],
        )
        print(
            "  Mean realised outcome:",
            chip["outcome_mean"],
        )

        if chip.get(
            "archetypes"
        ):
            print(
                "  FH archetypes:"
            )

            for archetype in chip[
                "archetypes"
            ]:
                print(
                    "   ",
                    f"{archetype['label']}: "
                    f"{archetype['case_count']} cases · "
                    f"Spearman {archetype['spearman']} · "
                    f"mean outcome "
                    f"{archetype['outcome_mean']}",
                )

        if chip.get(
            "fh_diagnostics"
        ):
            print(
                "  FH pre-deadline proxy diagnostics:"
            )
            blankers_unmeasurable = False
            unresolved_teams = set()

            for index, diagnostic in enumerate(
                chip["fh_diagnostics"],
                start=1,
            ):
                template_xi = (
                    diagnostic[
                        "template_xi"
                    ]
                    or {}
                )
                free_hit_xi = (
                    diagnostic[
                        "free_hit_xi"
                    ]
                    or {}
                )
                player_pool = (
                    diagnostic[
                        "player_pool"
                    ]
                    or {}
                )
                print(
                    "   ",
                    f"{diagnostic['season']} "
                    f"GW{diagnostic['gameweek']} "
                    f"({diagnostic['kind']}): "
                    f"template {diagnostic['template_score']} · "
                    f"FH {diagnostic['free_hit_score']} · "
                    f"uplift {diagnostic['uplift']:.1f}",
                )
                print(
                    "     ",
                    "Pre-deadline projections "
                    f"template {diagnostic['template_projection']} · "
                    f"FH {diagnostic['free_hit_projection']} · "
                    "omniscient ceiling "
                    f"{diagnostic['omniscient_score']} "
                    f"(uplift {diagnostic['omniscient_uplift']})",
                )
                print(
                    "     ",
                    "Player-fixtures "
                    f"template XI "
                    f"{template_xi.get('player_fixtures')} · "
                    f"FH XI "
                    f"{free_hit_xi.get('player_fixtures')} · "
                    "zero-fixture template players "
                    f"{template_xi.get('zero_fixture_players')}",
                )

                if not player_pool.get(
                    "can_measure_template_blankers",
                    False,
                ):
                    blankers_unmeasurable = True

                unresolved_teams.update(
                    player_pool.get(
                        "unresolved_teams",
                        [],
                    )
                )

                if index <= 3:
                    print(
                        "      Template XI:",
                        _format_lineup(
                            diagnostic[
                                "template_xi"
                            ],
                            diagnostic[
                                "template_captain"
                            ],
                        ),
                    )
                    print(
                        "      Free Hit XI:",
                        _format_lineup(
                            diagnostic[
                                "free_hit_xi"
                            ],
                            diagnostic[
                                "free_hit_captain"
                            ],
                        ),
                    )

            if blankers_unmeasurable:
                print(
                    "    DATA LIMIT: the outcome player pools "
                    "contain no zero-fixture players, so "
                    "template blankers cannot be measured."
                )

            if unresolved_teams:
                print(
                    "    DATA LIMIT: unresolved historical teams:",
                    ", ".join(
                        sorted(
                            unresolved_teams
                        )
                    ),
                )
        print(
            "  Highest signal:"
        )

        for row in chip[
            "strongest_signal"
        ]:
            print(
                "   ",
                _format_case(
                    row
                ),
            )

        print(
            "  Highest realised outcome:"
        )

        for row in chip[
            "strongest_outcome"
        ]:
            print(
                "   ",
                _format_case(
                    row
                ),
            )

        print()

    print(
        "CAUTION:",
        report["note"],
    )


if __name__ == "__main__":
    main()
