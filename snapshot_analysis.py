from history_store import (
    get_gameweek_snapshot_payloads,
)


CHECKPOINT_ORDER = {
    "baseline": 0,
    "t60m": 1,
    "t15m": 2,
    "t10m": 3,
    "t5m": 4,
}


def _player_state(payload):
    bootstrap = payload.get(
        "bootstrap",
        {},
    )

    result = {}

    for player in bootstrap.get(
        "elements",
        [],
    ):
        player_id = player.get("id")

        if player_id is None:
            continue

        result[int(player_id)] = {
            "status":
                player.get("status"),
            "chance_next":
                player.get(
                    "chance_of_playing_next_round"
                ),
            "price":
                player.get("now_cost"),
            "news":
                player.get("news"),
            "ep_next":
                player.get("ep_next"),
        }

    return result


def _fixture_state(payload):
    result = {}

    for fixture in payload.get(
        "fixtures",
        [],
    ):
        fixture_id = fixture.get("id")

        if fixture_id is None:
            continue

        result[int(fixture_id)] = {
            "event":
                fixture.get("event"),
            "kickoff_time":
                fixture.get("kickoff_time"),
            "team_h":
                fixture.get("team_h"),
            "team_a":
                fixture.get("team_a"),
            "team_h_difficulty":
                fixture.get(
                    "team_h_difficulty"
                ),
            "team_a_difficulty":
                fixture.get(
                    "team_a_difficulty"
                ),
        }

    return result


def _team_state(payload):
    current_team = payload.get(
        "current_team",
        {},
    )

    picks = tuple(
        sorted(
            (
                pick.get("element"),
                pick.get("position"),
                pick.get("selling_price"),
                bool(
                    pick.get("is_captain")
                ),
                bool(
                    pick.get(
                        "is_vice_captain"
                    )
                ),
            )
            for pick in current_team.get(
                "picks",
                [],
            )
        )
    )

    transfers = current_team.get(
        "transfers",
        {},
    )

    chips = tuple(
        sorted(
            (
                chip.get("name"),
                chip.get("number"),
                chip.get(
                    "status_for_entry"
                )
                or chip.get("status"),
                chip.get(
                    "played_by_entry"
                )
                or chip.get(
                    "played_event"
                ),
            )
            for chip in current_team.get(
                "chips",
                [],
            )
        )
    )

    return {
        "picks":
            picks,
        "bank":
            transfers.get("bank"),
        "limit":
            transfers.get("limit"),
        "made":
            transfers.get("made"),
        "cost":
            transfers.get("cost"),
        "chips":
            chips,
    }


def _changed_ids(before, after):
    ids = set(before) | set(after)

    return [
        item_id
        for item_id in ids
        if before.get(item_id)
        != after.get(item_id)
    ]


def compare_snapshot_payloads(
    before,
    after,
):
    before_players = _player_state(
        before
    )
    after_players = _player_state(
        after
    )

    player_ids = _changed_ids(
        before_players,
        after_players,
    )

    availability_changes = []

    for player_id in player_ids:
        old = before_players.get(
            player_id,
            {},
        )
        new = after_players.get(
            player_id,
            {},
        )

        if (
            old.get("status")
            != new.get("status")
            or
            old.get("chance_next")
            != new.get("chance_next")
            or
            old.get("news")
            != new.get("news")
        ):
            availability_changes.append(
                player_id
            )

    price_changes = [
        player_id
        for player_id in player_ids
        if before_players.get(
            player_id,
            {},
        ).get("price")
        != after_players.get(
            player_id,
            {},
        ).get("price")
    ]

    projection_input_changes = [
        player_id
        for player_id in player_ids
        if before_players.get(
            player_id,
            {},
        ).get("ep_next")
        != after_players.get(
            player_id,
            {},
        ).get("ep_next")
    ]

    fixture_changes = _changed_ids(
        _fixture_state(before),
        _fixture_state(after),
    )

    team_changed = (
        _team_state(before)
        != _team_state(after)
    )

    material_count = (
        len(availability_changes)
        + len(price_changes)
        + len(fixture_changes)
        + int(team_changed)
    )

    return {
        "players_changed":
            len(player_ids),
        "availability_changes":
            len(availability_changes),
        "price_changes":
            len(price_changes),
        "projection_input_changes":
            len(projection_input_changes),
        "fixture_changes":
            len(fixture_changes),
        "team_state_changed":
            team_changed,
        "material_changes":
            material_count,
    }


def analyse_gameweek_snapshots(
    gameweek,
    entry_id,
    db_path=None,
):
    kwargs = {}

    if db_path is not None:
        kwargs["db_path"] = db_path

    snapshots = (
        get_gameweek_snapshot_payloads(
            gameweek,
            entry_id,
            **kwargs,
        )
    )

    snapshots = sorted(
        snapshots,
        key=lambda item:
            CHECKPOINT_ORDER.get(
                item.get("checkpoint"),
                99,
            ),
    )

    comparisons = []

    for before, after in zip(
        snapshots,
        snapshots[1:],
    ):
        comparison = (
            compare_snapshot_payloads(
                before["payload"],
                after["payload"],
            )
        )

        comparison.update({
            "from_checkpoint":
                before["checkpoint"],
            "to_checkpoint":
                after["checkpoint"],
            "from_captured_at":
                before["captured_at"],
            "to_captured_at":
                after["captured_at"],
        })

        comparisons.append(
            comparison
        )

    return {
        "gameweek":
            int(gameweek),
        "snapshot_count":
            len(snapshots),
        "comparisons":
            comparisons,
        "ready":
            len(snapshots) >= 2,
    }
