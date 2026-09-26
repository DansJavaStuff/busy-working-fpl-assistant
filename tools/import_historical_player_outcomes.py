from historical_outcome_importer import (
    import_historical_player_outcomes_all,
)


def main():
    result = (
        import_historical_player_outcomes_all()
    )

    print(
        "Historical player/Gameweek outcomes imported"
    )
    print(
        "Source commit:",
        result["resolved_commit"],
    )

    for season in result["seasons"]:
        print(
            f"{season['season']}: "
            f"{season['rows']} player-GW rows · "
            f"{season['gameweeks']} Gameweeks"
        )


if __name__ == "__main__":
    main()
