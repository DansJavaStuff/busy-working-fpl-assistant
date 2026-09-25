import argparse

from historical_importer import (
    DEFAULT_SEASONS,
    DEFAULT_SOURCE_REF,
    import_historical_seasons,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Import historical FPL teams "
            "and fixtures into SQLite."
        )
    )

    parser.add_argument(
        "seasons",
        nargs="*",
        default=list(
            DEFAULT_SEASONS
        ),
        help=(
            "Season keys such as "
            "2024-25. Defaults to the "
            "last five completed seasons."
        ),
    )

    parser.add_argument(
        "--source-ref",
        default=DEFAULT_SOURCE_REF,
        help=(
            "Git ref to resolve and pin "
            "before importing."
        ),
    )

    args = parser.parse_args()

    result = import_historical_seasons(
        seasons=args.seasons,
        source_ref=args.source_ref,
    )

    print(
        "Historical FPL import complete"
    )
    print(
        "Source commit:",
        result["resolved_commit"],
    )

    for season in result["seasons"]:
        print(
            f"{season['season']}: "
            f"{season['teams']} teams, "
            f"{season['fixtures']} fixtures, "
            f"{season['unassigned_fixtures']} "
            "unassigned"
        )


if __name__ == "__main__":
    main()
