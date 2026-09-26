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
