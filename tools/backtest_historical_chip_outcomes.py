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


def _format_captain_sanity(
    captain,
):
    if not captain:
        return "unavailable"

    return (
        f"{captain['player']} · ownership rank "
        f"{captain['ownership_rank']}/"
        f"{captain['candidate_count']} · season apps "
        f"{captain['season_appearances']} · recent apps "
        f"{captain['recent_appearances']}"
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
                if model[
                    "key"
                ] != "baseline":
                    paired = model[
                        "paired_baseline"
                    ]["overall"]
                    print(
                        "     ",
                        "Paired current proxy on the same "
                        f"{paired['case_count']} cases: "
                        f"Spearman {paired['spearman']} · "
                        "mean error "
                        f"{paired['mean_error']} · "
                        f"MAE {paired['mean_absolute_error']}",
                    )

        loso = chip.get(
            "blank_only_loso_validation"
        )

        if loso:
            print(
                "  Blank-only leave-one-season-out ranking:"
            )
            print(
                "   ",
                f"{loso['case_count']} cases · "
                "fixture signal Spearman "
                f"{loso['signal_spearman']} · "
                "regressed projection Spearman "
                f"{loso['projection_spearman']} · "
                "equal-rank blend Spearman "
                f"{loso['combined_spearman']}",
            )
            for season in loso[
                "seasons"
            ]:
                print(
                    "   ",
                    f"{season['season']}: "
                    f"{season['case_count']} cases · "
                    f"signal {season['signal_spearman']} · "
                    "projection "
                    f"{season['projection_spearman']} · "
                    f"blend {season['combined_spearman']}",
                )
            print(
                "   ",
                loso[
                    "mixed_blank_double_status"
                ],
            )

            stability = loso["ranking_stability"]
            print("  Blank-only FH ranking stability:")
            print(
                f"    {stability['status']} · preferred research model "
                f"{stability['preferred_research_model']} · improved seasons "
                f"{stability['improved_seasons']}/{stability['informative_seasons']}"
            )
            print(
                "    Mean top-week regret (points, equal season weight): "
                f"fixture {stability['fixture_mean_top_week_regret']} · "
                f"blend {stability['blend_mean_top_week_regret']}"
            )
            for season in stability["seasons"]:
                print(
                    f"    {season['season']}: delta {season['blend_delta']} · "
                    f"fixture top {season['fixture_top_week']} · "
                    f"blend top {season['blend_top_week']}"
                )
            print("    Season deletions of fixed out-of-fold scores (no refitting):")
            for deletion in stability["season_deletions"]:
                print(
                    f"      Without {deletion['omitted_season']}: "
                    f"{deletion['case_count']} cases · "
                    f"fixture {deletion['signal_spearman']} · "
                    f"blend {deletion['combined_spearman']} · "
                    f"delta {deletion['blend_delta']}"
                )
            for check in stability["checks"]:
                print(f"    {'PASS' if check['passed'] else 'FAIL'} {check['label']}")
            print("   ", stability["production_status"])

        calibration = chip.get(
            "player_calibration_validation"
        )

        if calibration:
            print(
                "  FH player-level calibration:"
            )
            print(
                "   ",
                calibration[
                    "training_policy"
                ],
            )
            diagnostics = calibration[
                "player_diagnostics"
            ]
            print(
                "    Optimiser-selection diagnostics:"
            )
            for row in (
                [diagnostics["overall"]]
                + diagnostics["by_role"]
            ):
                label = row.get(
                    "label",
                    "All active player-cases",
                )
                print(
                    "     ",
                    f"{label}: {row['player_count']} · "
                    f"Spearman {row['spearman']} · "
                    f"projected {row['projected_mean']} · "
                    f"actual {row['actual_mean']} · "
                    f"error {row['mean_error']} · "
                    f"MAE {row['mean_absolute_error']}",
                )
            for heading, key in (
                (
                    "By position",
                    "by_position",
                ),
                (
                    "By sample history",
                    "by_sample",
                ),
                (
                    "By projection band",
                    "by_projection_band",
                ),
            ):
                print(
                    f"    {heading}:"
                )
                for row in diagnostics[key]:
                    print(
                        "     ",
                        f"{row['label']}: "
                        f"{row['player_count']} · "
                        f"projected {row['projected_mean']} · "
                        f"actual {row['actual_mean']} · "
                        f"error {row['mean_error']} · "
                        f"MAE {row['mean_absolute_error']}",
                    )
            print(
                "    Leave-one-season-out rebuilt squads:"
            )
            for model in calibration[
                "models"
            ]:
                print(
                    "     ",
                    f"{model['label']}: "
                    f"{model['case_count']} cases · "
                    f"projection Spearman {model['spearman']} · "
                    f"fixture signal {model['signal_spearman']} · "
                    f"projected {model['projected_mean']} · "
                    f"realised {model['realised_mean']} · "
                    f"error {model['mean_error']} · "
                    f"MAE {model['mean_absolute_error']} · "
                    "GK/DEF captains "
                    f"{model['implausible_captain_count']} · "
                    "max starter projection "
                    f"{model['maximum_starter_projection']}",
                )
                for season in model[
                    "seasons"
                ]:
                    print(
                        "       ",
                        f"{season['season']}: "
                        f"{season['case_count']} cases · "
                        f"Spearman {season['spearman']} · "
                        f"realised {season['realised_mean']} · "
                        f"MAE {season['mean_absolute_error']}",
                    )
            acceptance = calibration[
                "candidate_acceptance"
            ]
            print(
                "    Hybrid-calibration acceptance:",
                (
                    "PASS"
                    if acceptance["passed"]
                    else "HOLD"
                ),
            )
            for check in acceptance[
                "checks"
            ]:
                print(
                    "     ",
                    (
                        "PASS"
                        if check["passed"]
                        else "FAIL"
                    ),
                    f"{check['label']}: "
                    f"{check['candidate']} vs "
                    f"{check['benchmark']}",
                )
            print(
                "   ",
                calibration[
                    "mixed_blank_double_status"
                ],
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

            print(
                "  Largest-overprediction autopsies:"
            )
            for row in projection_errors[
                "largest_overprediction"
            ][:4]:
                template_xi = (
                    row.get("template_xi")
                    or {}
                )
                free_hit_xi = (
                    row.get("free_hit_xi")
                    or {}
                )
                captain_sanity = (
                    row.get(
                        "captain_sanity"
                    )
                    or {}
                )
                print(
                    "   ",
                    f"{row['season']} GW{row['gameweek']} "
                    f"({row['kind']}): blanks "
                    f"{row['blank_team_count']} · doubles "
                    f"{row['double_team_count']} · active teams "
                    f"{row['active_team_count']} · fixtures "
                    f"{row['scheduled_fixture_count']}",
                )
                print(
                    "     ",
                    f"Template {row['template_score']}pts/"
                    f"{row['template_projection']}pred · "
                    f"FH {row['free_hit_score']}pts/"
                    f"{row['free_hit_projection']}pred",
                )
                print(
                    "      Template XI:",
                    _format_lineup(
                        template_xi,
                        row[
                            "template_captain"
                        ],
                    ),
                )
                print(
                    "      Free Hit XI:",
                    _format_lineup(
                        free_hit_xi,
                        row[
                            "free_hit_captain"
                        ],
                    ),
                )
                print(
                    "     ",
                    "Template captain: "
                    f"{_format_captain_sanity(captain_sanity.get('template'))}",
                )
                print(
                    "     ",
                    "Free Hit captain: "
                    f"{_format_captain_sanity(captain_sanity.get('free_hit'))}",
                )
                print(
                    "     ",
                    "Small samples: template "
                    f"{_format_small_samples(template_xi)} · "
                    f"FH {_format_small_samples(free_hit_xi)}",
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

        if chip[
            "shape_breakdown"
        ]:
            print(
                "  By fixture shape:"
            )

            for shape in chip[
                "shape_breakdown"
            ]:
                print(
                    "   "
                    f"{shape['kind']}: "
                    f"{shape['case_count']} cases · "
                    f"Spearman {shape['spearman']} · "
                    f"mean outcome "
                    f"{shape['outcome_mean']} · "
                    f"range "
                    f"{shape['outcome_min']}"
                    f"–{shape['outcome_max']}"
                )

        print()

    print(
        "CAUTION:",
        report["note"],
    )


if __name__ == "__main__":
    main()
