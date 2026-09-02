import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

DATA_ROOT = (
    PROJECT_ROOT
    / "external"
    / "FPL-Core-Insights"
    / "data"
    / "2025-2026"
)

PLAYERS_FILE = DATA_ROOT / "players.csv"
PLAYERSTATS_FILE = DATA_ROOT / "playerstats.csv"


def safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default

        return float(value)

    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default

        return int(float(value))

    except (ValueError, TypeError):
        return default


def load_historical_players():
    """
    Load the final 2025/26 FPL snapshot for each player.

    Returns a dictionary keyed by FPL player code.

    Player code is preferred over player ID because IDs
    can change between FPL seasons.
    """

    if not PLAYERS_FILE.exists():
        return {}

    if not PLAYERSTATS_FILE.exists():
        return {}

    #
    # Map previous-season FPL element ID to the more
    # persistent player code.
    #
    id_to_player = {}

    with PLAYERS_FILE.open(
        newline="",
        encoding="utf-8",
    ) as handle:

        reader = csv.DictReader(handle)

        for row in reader:

            player_id = safe_int(
                row.get("player_id")
            )

            player_code = safe_int(
                row.get("player_code")
            )

            if not player_id or not player_code:
                continue

            id_to_player[player_id] = {
                "player_code": player_code,
                "first_name": row.get(
                    "first_name",
                    "",
                ),
                "second_name": row.get(
                    "second_name",
                    "",
                ),
                "web_name": row.get(
                    "web_name",
                    "",
                ),
                "position": row.get(
                    "position",
                    "",
                ),
            }

    #
    # Keep the highest-GW snapshot for each historical
    # player. The CSV is not guaranteed to be sorted.
    #
    latest_by_id = {}

    with PLAYERSTATS_FILE.open(
        newline="",
        encoding="utf-8",
    ) as handle:

        reader = csv.DictReader(handle)

        for row in reader:

            player_id = safe_int(
                row.get("id")
            )

            gw = safe_int(
                row.get("gw")
            )

            if not player_id:
                continue

            previous = latest_by_id.get(
                player_id
            )

            if (
                previous is None
                or gw > previous["gw"]
            ):
                latest_by_id[player_id] = {
                    "gw": gw,
                    "minutes": safe_int(
                        row.get("minutes")
                    ),
                    "starts": safe_int(
                        row.get("starts")
                    ),
                    "total_points": safe_float(
                        row.get("total_points")
                    ),
                    "points_per_game": safe_float(
                        row.get("points_per_game")
                    ),
                    "expected_goals": safe_float(
                        row.get("expected_goals")
                    ),
                    "expected_assists": safe_float(
                        row.get("expected_assists")
                    ),
                    "expected_goal_involvements": (
                        safe_float(
                            row.get(
                                "expected_goal_involvements"
                            )
                        )
                    ),
                    "expected_goals_per_90": (
                        safe_float(
                            row.get(
                                "expected_goals_per_90"
                            )
                        )
                    ),
                    "expected_assists_per_90": (
                        safe_float(
                            row.get(
                                "expected_assists_per_90"
                            )
                        )
                    ),
                    "expected_goal_involvements_per_90": (
                        safe_float(
                            row.get(
                                "expected_goal_involvements_per_90"
                            )
                        )
                    ),
                    "clean_sheets_per_90": (
                        safe_float(
                            row.get(
                                "clean_sheets_per_90"
                            )
                        )
                    ),
                    "saves_per_90": safe_float(
                        row.get("saves_per_90")
                    ),
                    "defensive_contribution_per_90": (
                        safe_float(
                            row.get(
                                "defensive_contribution_per_90"
                            )
                        )
                    ),
                }

    historical_players = {}

    for player_id, stats in latest_by_id.items():

        identity = id_to_player.get(
            player_id
        )

        if identity is None:
            continue

        player_code = identity[
            "player_code"
        ]

        historical_players[player_code] = {
            **identity,
            **stats,
        }

    return historical_players

def get_historical_position_priors(
    historical_players,
):
    """
    Calculate positional PPG priors from the final
    previous-season snapshots.

    Only players with at least 900 minutes are used
    so tiny samples do not distort the averages.
    """

    position_map = {
        "Goalkeeper": "GKP",
        "Defender": "DEF",
        "Midfielder": "MID",
        "Forward": "FWD",
    }

    samples = {
        "GKP": [],
        "DEF": [],
        "MID": [],
        "FWD": [],
    }

    for player in historical_players.values():

        if player["minutes"] < 900:
            continue

        position = position_map.get(
            player["position"]
        )

        if position is None:
            continue

        samples[position].append(
            player["points_per_game"]
        )

    priors = {}

    for position, values in samples.items():

        if values:
            priors[position] = (
                sum(values) / len(values)
            )

    return priors
