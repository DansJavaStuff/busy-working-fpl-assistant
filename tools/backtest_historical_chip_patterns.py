import argparse

from historical_pattern_backtest import (
    calibrate_all_chip_patterns,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Leave-one-season-out calibration "
            "of historical chip-pattern similarity."
        )
    )
    parser.add_argument(
        "--thresholds",
        nargs="*",
        type=float,
        default=[
            70,
            75,
            80,
            85,
            90,
        ],
    )
    args = parser.parse_args()

    report = calibrate_all_chip_patterns(
        thresholds=args.thresholds
    )

    print(
        "Historical chip-pattern calibration"
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
            f"{chip['matched_count']}/"
            f"{chip['case_count']} cases matched"
        )
        print(
            "  similarity "
            f"min {chip['similarity_min']} · "
            f"p25 {chip['similarity_p25']} · "
            f"median {chip['similarity_median']} · "
            f"p75 {chip['similarity_p75']} · "
            f"max {chip['similarity_max']}"
        )

        for threshold in chip[
            "thresholds"
        ]:
            coverage = threshold[
                "coverage"
            ]
            print(
                f"  >= {threshold['threshold']:.0f}%: "
                f"{threshold['passing']}/"
                f"{threshold['matched_cases']} "
                f"({coverage if coverage is not None else 'n/a'}%)"
            )

        print()

    print(
        "Note: fixture-pattern calibration only; "
        "realised chip-point outcomes are not yet "
        "part of the historical database."
    )


if __name__ == "__main__":
    main()
