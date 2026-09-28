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


def _format_small_samples(
    lineup,
):
    players = lineup.get(
        "small_sample_players",
        [],
    )

    if not players:
        return "none"

    return (
        f"{len(players)} "
        f"({', '.join(players)})"
    )


def _format_projection_case(
    row,
):
    return (
        f"{row['season']} GW{row['gameweek']} "
        f"({row['kind']}): projected "
        f"{row['projected_uplift']:.1f} · realised "
        f"{row['realised_uplift']:.1f} · error "
        f"{row['error']:+.1f} · XI "
        f"{row['starter_projected_uplift']:+.1f} · captain "
        f"{row['captain_projected_uplift']:+.1f}"
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

        projection_validation = chip.get(
            "projection_validation"
        )

        if projection_validation:
            print(
                "  Spearman projected uplift/outcome:",
                projection_validation[
                    "projected_spearman"
                ],
                f"({projection_validation['projected_case_count']} cases)",
            )
            print(
                "  Mean projected uplift:",
                projection_validation[
                    "projected_uplift_mean"
                ],
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
                    "projected-uplift Spearman "
                    f"{archetype['projected_spearman']} · "
                    f"mean outcome "
                    f"{archetype['outcome_mean']}",
                )

        if chip.get(
            "sensitivity_models"
        ):
            print(
                "  FH projection sensitivity models:"
            )

            for model in chip[
                "sensitivity_models"
            ]:
                overall = model[
                    "overall"
                ]
                blank_only = model[
                    "blank_only"
                ]
                blank_double = model[
                    "blank_double"
                ]
                print(
                    "   ",
                    f"{model['label']}: "
                    f"{overall['case_count']} cases · "
                    f"Spearman {overall['spearman']} · "
                    f"projected {overall['projected_mean']} · "
                    f"realised {overall['realised_mean']} · "
                    "mean error (projected-realised) "
                    f"{overall['mean_error']} · "
                    f"MAE {overall['mean_absolute_error']}",
                )
                print(
                    "     ",
                    "Components: XI "
                    f"{overall['starter_projected_mean']} · "
                    "captain "
                    f"{overall['captain_projected_mean']} · "
                    "blank-only Spearman "
                    f"{blank_only['spearman']} · "
                    "mixed Spearman "
                    f"{blank_double['spearman']}",
                )

        projection_errors = chip.get(
            "projection_error_diagnostics"
        )

        if projection_errors:
            for label, key in (
                (
                    "Highest projected uplift",
                    "highest_projected",
                ),
                (
                    "Largest overprediction",
                    "largest_overprediction",
                ),
                (
                    "Largest underprediction",
                    "largest_underprediction",
                ),
            ):
                print(
                    f"  {label}:"
                )
                for row in projection_errors[
                    key
                ]:
                    print(
                        "   ",
                        _format_projection_case(
                            row
                        ),
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
                captain_sanity = (
                    diagnostic.get(
                        "captain_sanity"
                    )
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
                    for label, key in (
                        (
                            "Template captain",
                            "template",
                        ),
                        (
                            "Free Hit captain",
                            "free_hit",
                        ),
                    ):
                        captain = (
                            captain_sanity.get(
                                key
                            )
                            or {}
                        )
                        if captain:
                            print(
                                "     ",
                                f"{label}: "
                                f"ownership rank "
                                f"{captain['ownership_rank']}/"
                                f"{captain['candidate_count']} · "
                                f"season apps "
                                f"{captain['season_appearances']} · "
                                f"recent apps "
                                f"{captain['recent_appearances']} · "
                                f"recent minutes "
                                f"{captain['recent_minutes']}",
                            )
                    print(
                        "     ",
                        "Small-sample XI players "
                        "(<5 season or <2 recent apps) "
                        "template "
                        f"{_format_small_samples(template_xi)} · "
                        "FH "
                        f"{_format_small_samples(free_hit_xi)}",
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

        excluded_unplayable = chip.get(
            "excluded_unplayable",
            [],
        )

        if excluded_unplayable:
            print(
                "  Excluded unplayable slates:"
            )
            for row in excluded_unplayable:
                print(
                    "   ",
                    f"{row['season']} GW{row['gameweek']} · "
                    f"signal {row['signal']:.1f} · "
                    f"{row['reason']}",
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
