import hashlib
import json
from itertools import combinations

from fpl_api import (
    get_bootstrap,
    get_fixtures,
    get_my_team,
    get_planning_gameweek,
)

from optimizer import (
    load_players,
    optimise_squad,
    calculate_objective_score,
    calculate_captain_score,
)

from transfer_optimizer import (
    optimise_transfers,
)

from history_store import (
    get_cached_result,
    save_cached_result,
)

from historical_analogues import (
    current_historical_analogues,
)


POST_BB_HORIZON_WEIGHT = 0.15
FIRST_HALF_END_GW = 19
SECOND_HALF_START_GW = 20
SEASON_END_GW = 38

CHIP_CACHE_MODEL_VERSION = "chip-planner-v4"
CHIP_TIMING_WINDOW_MODEL_VERSION = "chip-timing-window-v1"
CHIP_PLANNER_CACHE_TTL = 15 * 60
CHIP_OPPORTUNITY_CACHE_TTL = 30 * 60