from collections import defaultdict

import pulp

from fpl_api import (
    get_bootstrap,
    get_fixtures,
    get_planning_gameweek,
)

from team_strength import (
    get_team_strengths,
    attacking_fixture_multiplier,
    defensive_fixture_multiplier,
)

from player_context import PLAYER_CONTEXT

from goalkeeper_depth import (
    get_goalkeeper_depth,
)

from outfield_depth import (
    get_outfield_depth,
)

BUDGET = 1000  # FPL stores prices in tenths: £100.0m = 1000

DEBUG = False

def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def fixture_multiplier(difficulty):
    """
    Convert FPL fixture difficulty into a simple points multiplier.
    Neutral fixture = 1.00
    """
    multipliers = {
        1: 1.18,
        2: 1.10,
        3: 1.00,
        4: 0.90,
        5: 0.82,
    }

    return multipliers.get(difficulty, 1.00)

def fallback_strength_from_fpl(team, home_or_away):
    """
    Convert FPL preseason overall strength (typically 2-5)
    into an approximate multiplier around 1.00.
    """

    if home_or_away == "home":
        raw = team.get("strength_overall_home")
    else:
        raw = team.get("strength_overall_away")

    raw = safe_float(raw, 3.0)

    mapping = {
        2: 0.85,
        3: 1.00,
        4: 1.15,
        5: 1.30,
    }

    return mapping.get(
        int(round(raw)),
        1.00
    )
    
def project_gameweeks(
    player,
    fixtures,
    planning_gameweek,
):

    ppg = player["points_per_game"]
    ep_next = player["ep_next"]
    minutes = player["minutes"]

    current_season_games = player.get(
        "current_season_games",
        0
    )

    current_season_weight = min(
        current_season_games / 6.0,
        1.0
    )

    position = player["position"]

    position_prior = player.get(
        "position_prior",
        3.5
    )
    
    xgi90 = player["xgi90"]
    clean_sheets90 = player["clean_sheets90"]
    defensive90 = player["defensive90"]
    saves90 = player["saves90"]

    #
    # Reliability based on historical minutes.
    #
    historical_reliability = min(
        minutes / 1800,
        1.0
    )

    reliability = historical_reliability

    context = PLAYER_CONTEXT.get(
        player["name"],
        {}
    )

    expected_start_probability = context.get(
        "expected_start_probability",
    )
    
    if expected_start_probability is None:

        keeper_info = player.get(
            "goalkeeper_depth",
            {}
        )
        
        if keeper_info:

            expected_start_probability = (
                keeper_info[
                    "expected_start_probability"
                ]
            )

        elif player["position"] == "GKP":

            #
            # FPL goalkeeper who does not appear
            # on the external depth chart.
            #
            # Assume extremely unlikely to start.
            #
            expected_start_probability = 0.01

        else:

            expected_start_probability = 1.0

    #
    # Historical baseline.
    #
    adjusted_ppg = (
        ppg * current_season_weight
        + position_prior
        * (1.0 - current_season_weight)
    )

    historical_baseline = (
        adjusted_ppg * reliability
        + position_prior
        * (1.0 - reliability)
    )

    #
    # Underlying-performance adjustment.
    #

    if position == "GKP":

        underlying_adjustment = (
            clean_sheets90 * 0.8
            + saves90 * 0.15
        )

    elif position == "DEF":

        underlying_adjustment = (
            clean_sheets90 * 0.7
            + xgi90 * 1.5
            + defensive90 * 0.03
        )

    elif position == "MID":

        underlying_adjustment = (
            xgi90 * 1.8
            + defensive90 * 0.015
        )

    elif position == "FWD":

        underlying_adjustment = (
            xgi90 * 2.0
        )

    else:

        underlying_adjustment = 0.0

    underlying_adjustment *= reliability

    projected_baseline = (
        historical_baseline * 0.85
        + underlying_adjustment * 0.15
    )

    projections = {}

    for gw in range(
        planning_gameweek,
        planning_gameweek + 5
    ):

        fixture = next(
            (
                f
                for f in fixtures
                if f["gw"] == gw
            ),
            None
        )

        if fixture is None:
            projections[gw] = 0.0
            continue

                #
        # V4 fixture model:
        #
        # Goalkeepers and defenders primarily care about
        # the opponent's attacking strength.
        #
        # Midfielders and forwards primarily care about
        # the opponent's defensive strength.
        #
        if position in {
            "GKP",
            "DEF",
        }:

            multiplier = fixture.get(
                "defence_multiplier",
                fixture_multiplier(
                    fixture["difficulty"]
                )
            )

        else:

            multiplier = fixture.get(
                "attack_multiplier",
                fixture_multiplier(
                    fixture["difficulty"]
                )
            )

        if (
            gw == planning_gameweek
            and ep_next > 0
        ):

            baseline = (
                ep_next * 0.40
                + projected_baseline * 0.60
            )

            #
            # ep_next is already fixture-aware.
            # Apply only 35% of our own fixture adjustment
            # in the planning gameweek to avoid
            # double-counting the fixture.
            #

            gw1_multiplier = 1.0 + (
                (multiplier - 1.0) * 0.35
            )

            projected = (
                baseline * gw1_multiplier
            )

        else:

            baseline = projected_baseline

            projected = (
                baseline * multiplier
            )

            projected *= (
                expected_start_probability
            )
        projections[gw] = projected

    #
    # Diagnostic information.
    #
    projections["_debug"] = {
        "ppg": ppg,
        "ep_next": ep_next,
        "reliability": reliability,
        "historical_baseline": historical_baseline,
        "underlying_adjustment": underlying_adjustment,
        "projected_baseline": projected_baseline,
        "expected_start_probability": expected_start_probability,
        "current_season_weight": current_season_weight,
        "adjusted_ppg": adjusted_ppg,
    }

    return projections

def build_fixture_scores(
    teams,
    team_data,
    historical_team_strengths,
    planning_gameweek,
):

    fixtures = get_fixtures()

    # Earlier gameweeks matter more
    planning_gameweek,
    gw_weights = {
        planning_gameweek: 1.00,
        planning_gameweek + 1: 0.90,
        planning_gameweek + 2: 0.80,
        planning_gameweek + 3: 0.70,
        planning_gameweek + 4: 0.60,
    }

    #
    # Convert FPL difficulty into a positive score:
    #
    # Difficulty 1 -> 5 points
    # Difficulty 2 -> 4
    # Difficulty 3 -> 3
    # Difficulty 4 -> 2
    # Difficulty 5 -> 1
    #
    difficulty_score = {
        1: 5.0,
        2: 4.0,
        3: 3.0,
        4: 2.0,
        5: 1.0,
    }

    fixture_scores = {}
    fixture_details = {}

    for fixture in fixtures:

        gw = fixture.get("event")

        if gw not in gw_weights:
            continue

        home_team = fixture["team_h"]
        away_team = fixture["team_a"]

        home_difficulty = fixture["team_h_difficulty"]
        away_difficulty = fixture["team_a_difficulty"]

        weight = gw_weights[gw]

        home_score = (
            difficulty_score[home_difficulty]
            * weight
        )

        away_score = (
            difficulty_score[away_difficulty]
            * weight
        )

        fixture_scores[home_team] = (
            fixture_scores.get(home_team, 0)
            + home_score
        )

        fixture_scores[away_team] = (
            fixture_scores.get(away_team, 0)
            + away_score
        )

        #
        # HOME TEAM'S FIXTURE
        #
        # Their opponent is the away team, so when falling
        # back to FPL strength we use the opponent's AWAY
        # strength.
        #

        home_opponent_name = teams[
            away_team
        ]

        home_opponent_history = (
            historical_team_strengths.get(
                home_opponent_name
            )
        )

        if home_opponent_history:

            home_opponent_attack = (
                home_opponent_history[
                    "attack_strength"
                ]
            )

            home_opponent_defence = (
                home_opponent_history[
                    "defence_strength"
                ]
            )

            home_strength_source = (
                "historical"
            )

        else:

            fallback = (
                fallback_strength_from_fpl(
                    team_data[away_team],
                    "away"
                )
            )

            home_opponent_attack = fallback
            home_opponent_defence = fallback

            home_strength_source = "fpl"

        home_attack_multiplier = (
            attacking_fixture_multiplier(
                home_opponent_defence
            )
        )

        home_defence_multiplier = (
            defensive_fixture_multiplier(
                home_opponent_attack
            )
        )

        fixture_details.setdefault(
            home_team,
            []
        ).append({
            "gw": gw,
            "difficulty": home_difficulty,
            "home": True,
            "opponent": away_team,
            "opponent_name": home_opponent_name,
            "opponent_attack": home_opponent_attack,
            "opponent_defence": home_opponent_defence,
            "attack_multiplier": home_attack_multiplier,
            "defence_multiplier": home_defence_multiplier,
            "strength_source": home_strength_source,
        })


        #
        # AWAY TEAM'S FIXTURE
        #
        # Their opponent is the home team, so when falling
        # back to FPL strength we use the opponent's HOME
        # strength.
        #

        away_opponent_name = teams[
            home_team
        ]

        away_opponent_history = (
            historical_team_strengths.get(
                away_opponent_name
            )
        )

        if away_opponent_history:

            away_opponent_attack = (
                away_opponent_history[
                    "attack_strength"
                ]
            )

            away_opponent_defence = (
                away_opponent_history[
                    "defence_strength"
                ]
            )

            away_strength_source = (
                "historical"
            )

        else:

            fallback = (
                fallback_strength_from_fpl(
                    team_data[home_team],
                    "home"
                )
            )

            away_opponent_attack = fallback
            away_opponent_defence = fallback

            away_strength_source = "fpl"

        away_attack_multiplier = (
            attacking_fixture_multiplier(
                away_opponent_defence
            )
        )

        away_defence_multiplier = (
            defensive_fixture_multiplier(
                away_opponent_attack
            )
        )

        fixture_details.setdefault(
            away_team,
            []
        ).append({
            "gw": gw,
            "difficulty": away_difficulty,
            "home": False,
            "opponent": home_team,
            "opponent_name": away_opponent_name,
            "opponent_attack": away_opponent_attack,
            "opponent_defence": away_opponent_defence,
            "attack_multiplier": away_attack_multiplier,
            "defence_multiplier": away_defence_multiplier,
            "strength_source": away_strength_source,
        })

    return fixture_scores, fixture_details

def calculate_availability_factor(
    fpl_status,
    fpl_chance,
    rotowire_status=None,
):
    """
    Estimate availability for the next gameweek.

    FPL is the primary source when it provides an explicit
    chance-of-playing percentage.

    RotoWire is used as a secondary source when FPL has not
    supplied a percentage.
    """

    # FPL gives us an explicit probability.
    if fpl_chance is not None:
        return safe_float(fpl_chance) / 100.0

    # FPL has flagged the player, but supplied no percentage.
    if fpl_status != "a":
        return 0.5

    # FPL thinks the player is available, so use RotoWire
    # as a secondary warning source.
    if rotowire_status == "OUT":
        return 0.05

    if rotowire_status == "SUS":
        return 0.05

    if rotowire_status == "GTD":
        return 0.75

    return 1.0

def load_players():
    data = get_bootstrap()
    
    goalkeeper_depth = (
        get_goalkeeper_depth()
    )

    outfield_depth, _ = (
        get_outfield_depth()
    )
    
    planning_gameweek = (
        get_planning_gameweek()
    )

    completed_gameweeks = max(0,planning_gameweek - 1)

    historical_team_strengths = get_team_strengths()

    teams = {
        team["id"]: team["name"]
        for team in data["teams"]
    }

    team_data = {
        team["id"]: team
        for team in data["teams"]
    }

    fixture_scores, fixture_details = (
        build_fixture_scores(
            teams,
            team_data,
            historical_team_strengths,
            planning_gameweek,
        )
    )   
    if DEBUG:

        print()
        print("HISTORICAL TEAM STRENGTH MATCHING")
        print("-" * 72)

        for team_id, team_name in teams.items():

            strength = historical_team_strengths.get(
                team_name
            )

            if strength:

                print(
                    f"{team_name:20} "
                    f"ATT {strength['attack_strength']:5.2f} "
                    f"DEF {strength['defence_strength']:5.2f} "
                )

            else:

                print(
                    f"{team_name:20} "
                    f"NO HISTORICAL PL DATA"
                )

    positions = {
        position["id"]: position["singular_name_short"]
        for position in data["element_types"]
    }

    #
    # Calculate positional PPG priors from players
    # with a meaningful historical sample.
    #
    position_samples = defaultdict(list)

    for p in data["elements"]:

        minutes = safe_float(
            p.get("minutes") 
        )

        ppg = safe_float(
            p.get("points_per_game")
        )

        if minutes < 900:
            continue

        position = positions[
            p["element_type"]
        ]

        position_samples[
            position
        ].append(ppg) 

    position_priors = {}

    for position, values in position_samples.items():

        if values:
            position_priors[position] = (
                sum(values) / len(values)
            )
    if DEBUG:
        print() 
        print("POSITIONAL PPG PRIORS")
        print()

        for position in ["GKP", "DEF", "MID", "FWD"]:

            print(
                f"{position}: "
                f"{position_priors.get(position, 3.5):.2f} "
                f"({len(position_samples.get(position, []))} players)"
            )

    players = []

    for p in data["elements"]:

        # Ignore players FPL says cannot currently be selected
        if not p.get("can_select", True):
            continue

        # A very simple first-pass GW1 rating.
        #
        # ep_next gets most of the weight because it is FPL's current
        # next-gameweek estimate.
        #
        # Last-season points and minutes provide some history/reliability.

        ep_next = safe_float(p.get("ep_next"))
        total_points = safe_float(p.get("total_points"))
        minutes = safe_float(p.get("minutes"))
        starts = safe_float(p.get("starts"))
        ownership = safe_float(p.get("selected_by_percent"))

        season_points_per_game = safe_float(p.get("points_per_game"))

        xg90 = safe_float(
            p.get("expected_goals_per_90")
        )

        xa90 = safe_float(
            p.get("expected_assists_per_90")
        )

        xgi90 = safe_float(
            p.get("expected_goal_involvements_per_90")
        )

        clean_sheets90 = safe_float(
            p.get("clean_sheets_per_90")
        )

        defensive90 = safe_float(
            p.get("defensive_contribution_per_90")
        )

        saves90 = safe_float(
            p.get("saves_per_90")
        )

        # Minutes reliability:
        # 3420 = 38 full matches
        minutes_factor = min(minutes / 3420, 1.0)

        # Reliability for per-90 stats.
        # Full strength at 1800+ minutes, heavily reduced for tiny samples.
        per90_reliability = min(minutes / 1800, 1.0)

        xg90_adj = xg90 * per90_reliability
        xa90_adj = xa90 * per90_reliability
        xgi90_adj = xgi90 * per90_reliability
        clean_sheets90_adj = clean_sheets90 * per90_reliability
        defensive90_adj = defensive90 * per90_reliability
        saves90_adj = saves90 * per90_reliability

        # Initial rating.
        fixture_score = fixture_scores.get(
            p["team"],
            0.0
        )

        position = positions[p["element_type"]]

        #
        # Base score shared by all positions
        #
        base_rating = (
            ep_next * 4.0
            + season_points_per_game * 3.0
            + minutes_factor * 3.0
            + fixture_score * 1.2
        )

        #
        # Position-specific upside
        #
        if position == "GKP":

            position_rating = (
                clean_sheets90_adj * 8.0
                + saves90_adj * 1.5
            )

        elif position == "DEF":

            position_rating = (
                clean_sheets90_adj * 7.0
                + xgi90_adj * 12.0
                + defensive90_adj * 0.30
            )

        elif position == "MID":

            position_rating = (
                xgi90_adj * 15.0
                + xg90_adj * 5.0
                + xa90_adj * 5.0
                + defensive90_adj * 0.15
            )

        elif position == "FWD":

            position_rating = (
                xgi90_adj * 18.0
                + xg90_adj * 7.0
                + xa90_adj * 3.0
            )

        else:

            position_rating = 0.0

        rating = (
            base_rating
            + position_rating
        )

        status = p.get(
            "status",
            "a"
        )

        chance = p.get(
            "chance_of_playing_next_round"
        )

        outfield_info = (
            outfield_depth.get(
                p["id"],
                {}
            )
        )

        rotowire_status = (
            outfield_info.get(
                "rotowire_status"
            )
        )

        availability_factor = (
            calculate_availability_factor(
                status,
                chance,
                rotowire_status,
            )
        )

        rating *= availability_factor

        player_fixture_details = fixture_details.get(
            p["team"],
            []
        )

        projection_input = {
            "current_season_games":completed_gameweeks, 
            "id": p["id"],
            "name": p["web_name"],
            "points_per_game": season_points_per_game,
            "ep_next": ep_next,
            "minutes": int(minutes),
            "position": position,
            "position_prior": position_priors.get(
                position,
                3.5
            ),
            "xgi90": xgi90,
            "clean_sheets90": clean_sheets90,
            "defensive90": defensive90,
            "saves90": saves90,
            "goalkeeper_depth": (
                goalkeeper_depth.get(
                    p["id"],
                    {}
                )
            ),
        }

        projections = project_gameweeks(
            projection_input,
            player_fixture_details,
            planning_gameweek,
        )

        projection_debug = projections["_debug"]

        projected_gameweeks = range(
            planning_gameweek,
            planning_gameweek + 5
        )

        projection_fields = {
            f"proj_gw{gw}": projections[gw]
            for gw in projected_gameweeks
        }

        projection_fields[
            f"proj_gw{planning_gameweek}"
        ] *= availability_factor

        # For now only heavily penalise GW1.
        # Longer-term projections retain most of their value because
        # an injury/doubt may clear before later gameweeks.
        proj_5gw = sum(
            projection_fields[
                f"proj_gw{gw}"
            ]
            for gw in projected_gameweeks
        )

        players.append({
            "id": p["id"],
            "name": p["web_name"],
            "team_id": p["team"],
            "team": teams[p["team"]],
            "position": positions[p["element_type"]],
            "position_id": p["element_type"],
            "cost": p["now_cost"],
            "price": p["now_cost"] / 10,
            "ep_next": ep_next,
            "points_per_game": season_points_per_game,
            "total_points": total_points,
            "minutes": int(minutes),
            "starts": int(starts),
            "ownership": ownership,
            "status": status,
            "fixture_score": fixture_score,
            "fixtures": player_fixture_details,
            "rating": rating,
            "xg90": xg90,
            "xa90": xa90,
            "xgi90": xgi90,
            "clean_sheets90": clean_sheets90,
            "defensive90": defensive90,
            "saves90": saves90,
            "planning_gameweek":
                planning_gameweek,
            "proj_next":
                projection_fields[
                    f"proj_gw{planning_gameweek}"
                ],
            **projection_fields,
            "proj_5gw": proj_5gw,
            "chance_of_playing_next_round": (
                p.get(
                    "chance_of_playing_next_round"
                )
            ),
            "rotowire_group": (
                outfield_info.get(
                    "position"
                )
            ),
            "rotowire_status": (
                outfield_info.get(
                    "rotowire_status"
                )
            ),
            "rotowire_order": (
                outfield_info.get(
                    "rotowire_order"
                )
            ),
            "projection_debug":
                projection_debug,
        })
    if DEBUG:

        print()
        print("V4 FIXTURE STRENGTH TEST")
        print("-" * 90)

        for player_name in [
            "Haaland",
            "Gabriel",
            "B.Fernandes",
        ]:

            player = next(
                (
                    p for p in players
                    if p["name"] == player_name
                ),
                None
            )

            if not player:
                continue

            fixture = next(
                (
                    f
                    for f in fixture_details[
                        player["team_id"]
                    ]
                    if f["gw"] == 1
                ),
                None
            )

            if not fixture:
                continue

            print(
                f"{player_name:15} "
                f"vs {fixture['opponent_name']:18} "
                f"OppATT {fixture['opponent_attack']:5.2f}  "
                f"OppDEF {fixture['opponent_defence']:5.2f}  "
                f"AM {fixture['attack_multiplier']:5.2f}  "
                f"DM {fixture['defence_multiplier']:5.2f}  "
                f"[{fixture['strength_source']}]"
            )

    return players

def calculate_captain_score(player):
    """
    Captaincy score.

    Expected points remains the main factor, but captaincy should
    favour attacking upside rather than blindly selecting the player
    with the highest mean projection.
    """

    planning_gameweek = player[
        "planning_gameweek"
    ]

    projection = player.get(
        f"proj_gw{planning_gameweek}",
        0.0,
    )

    position = player["position"]

    score = projection

    if position == "FWD":
        score *= 1.15

    elif position == "MID":
        score *= 1.12

    elif position == "DEF":
        score *= 1.03

    elif position == "GKP":
        score *= 0.95

    return score

def optimise_squad(
    players,
    force_player_id=None,
    force_formation=None,
    minimum_objective_score=None,
    minimise_cost=False,
):

    problem = pulp.LpProblem(
        "FPL_Squad",
        (
            pulp.LpMinimize
            if minimise_cost
            else pulp.LpMaximize
        )
    )

    selected = {
        p["id"]: pulp.LpVariable(
            f"selected_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    starter = {
        p["id"]: pulp.LpVariable(
            f"starter_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    captain = {
        p["id"]: pulp.LpVariable(
            f"captain_{p['id']}",
            cat="Binary"
        )
        for p in players
    }

    #
    # OBJECTIVE
    #
    # Starter gets full value.
    #
    # Captain gets another full copy of their score,
    # because captain points are doubled.
    #
    # A bench player gets 15% of their score so that
    # the optimiser doesn't completely ignore bench quality.
    #

    SQUAD_HORIZON_WEIGHT = 0.15

    projection_objective = pulp.lpSum(
        (
            starter[p["id"]] * p["proj_next"]
            +
            captain[p["id"]] * calculate_captain_score(p)
            +
            selected[p["id"]]
            * p["proj_5gw"]
            * SQUAD_HORIZON_WEIGHT
        )
        for p in players
    )

    squad_cost = pulp.lpSum(
        selected[p["id"]] * p["cost"]
        for p in players
    )

    if minimise_cost:
        problem += squad_cost
    else:
        problem += projection_objective

    if minimum_objective_score is not None:
        problem += (
            projection_objective
            >= minimum_objective_score
        )
    
    #
    # SQUAD RULES
    #

    # Exactly 15 players
    problem += pulp.lpSum(
        selected[p["id"]]
        for p in players
    ) == 15

    # £100.0m budget
    problem += squad_cost <= BUDGET

    # Squad position requirements
    squad_positions = {
        "GKP": 2,
        "DEF": 5,
        "MID": 5,
        "FWD": 3,
    }

    for position, required in squad_positions.items():
        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["position"] == position
        ) == required

    # Maximum 3 players from one club
    teams = set(
        p["team_id"]
        for p in players
    )

    for team_id in teams:
        problem += pulp.lpSum(
            selected[p["id"]]
            for p in players
            if p["team_id"] == team_id
        ) <= 3

    #
    # STARTING XI RULES
    #

    # Exactly 11 starters
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
    ) == 11

    # A starter must be in the squad
    for p in players:
        problem += (
            starter[p["id"]]
            <= selected[p["id"]]
        )

    # Exactly one starting goalkeeper
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "GKP"
    ) == 1

    # Minimum 3 defenders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "DEF"
    ) >= 3

    # Maximum 5 defenders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "DEF"
    ) <= 5

    # Minimum 2 midfielders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "MID"
    ) >= 2

    # Maximum 5 midfielders
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "MID"
    ) <= 5

    # Minimum 1 forward
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "FWD"
    ) >= 1

    # Maximum 3 forwards
    problem += pulp.lpSum(
        starter[p["id"]]
        for p in players
        if p["position"] == "FWD"
    ) <= 3

    #
    # OPTIONAL FORCED FORMATION
    #
    # Format is:
    #   (DEF, MID, FWD)
    #
    # Example:
    #   (4, 4, 2) = 4-4-2
    #

    if force_formation is not None:

        defenders, midfielders, forwards = (
            force_formation
        )

        problem += pulp.lpSum(
            starter[p["id"]]
            for p in players
            if p["position"] == "DEF"
        ) == defenders

        problem += pulp.lpSum(
            starter[p["id"]]
            for p in players
            if p["position"] == "MID"
        ) == midfielders

        problem += pulp.lpSum(
            starter[p["id"]]
            for p in players
            if p["position"] == "FWD"
        ) == forwards

    #
    # CAPTAIN RULES
    #

    # Exactly one captain
    problem += pulp.lpSum(
        captain[p["id"]]
        for p in players
    ) == 1

    # Captain must be a starter
    for p in players:
        problem += (
            captain[p["id"]]
            <= starter[p["id"]]
        )
    
    #
    # OPTIONAL FORCED PLAYER
    #

    if force_player_id is not None:
        problem += selected[force_player_id] == 1
    #
    # SOLVE
    #

    problem.solve(
        pulp.COIN_CMD(
            path="/usr/bin/cbc",
            msg=False
        )
    )

    if pulp.LpStatus[problem.status] != "Optimal":
        raise RuntimeError(
            f"Optimisation failed: "
            f"{pulp.LpStatus[problem.status]}"
        )

    squad = []

    for p in players:

        if selected[p["id"]].value() == 1:

            player = p.copy()

            player["starter"] = (
                starter[p["id"]].value() == 1
            )

            player["captain"] = (
                captain[p["id"]].value() == 1
            )

            squad.append(player)

    vice_candidates = [
        p
        for p in squad
        if p["starter"]
        and not p["captain"]
    ]

    vice_captain = max(
        vice_candidates,
        key=calculate_captain_score,
    )

    for p in squad:
        p["vice_captain"] = (
            p["id"] == vice_captain["id"]
        )

    return squad

def calculate_objective_score(squad):

    SQUAD_HORIZON_WEIGHT = 0.15

    score = 0.0

    for p in squad:

        if p["starter"]:
            score += p["proj_next"]

        if p["captain"]:
            score += calculate_captain_score(p)

        score += (
            p["proj_5gw"]
            * SQUAD_HORIZON_WEIGHT
        )

    return score

def analyse_budget_efficiency(
    players,
    maximum_squad,
    tolerances=(0.10, 0.25, 0.50, 1.00),
):
    """Find the cheapest legal squad within each score tolerance."""

    maximum_score = calculate_objective_score(maximum_squad)
    maximum_cost = sum(p["cost"] for p in maximum_squad)
    results = []

    for tolerance in tolerances:
        minimum_score = maximum_score - tolerance
        value_squad = optimise_squad(
            players,
            minimum_objective_score=minimum_score,
            minimise_cost=True,
        )
        value_score = calculate_objective_score(value_squad)
        value_cost = sum(p["cost"] for p in value_squad)

        results.append({
            "tolerance": tolerance,
            "squad": value_squad,
            "score": value_score,
            "cost": value_cost,
            "saved": maximum_cost - value_cost,
            "score_lost": maximum_score - value_score,
        })

    print()
    print("=" * 92)
    print("BUDGET EFFICIENCY")
    print("=" * 92)
    print(
        f"Maximum projection : £{maximum_cost / 10:.1f}m "
        f"-> {maximum_score:.2f}"
    )

    print()
    print(
        f"{'Tolerance':>10} "
        f"{'Cost':>9} "
        f"{'Bank':>9} "
        f"{'Score':>9} "
        f"{'Lost':>9}"
    )
    print("-" * 52)

    for result in results:
        print(
            f"{result['tolerance']:9.2f} "
            f"£{result['cost'] / 10:7.1f}m "
            f"£{(BUDGET - result['cost']) / 10:7.1f}m "
            f"{result['score']:9.2f} "
            f"{result['score_lost']:9.2f}"
        )

    preferred = next(
        result for result in results
        if abs(result["tolerance"] - 0.25) < 0.001
    )

    print()
    print("0.25-POINT NEAR-OPTIMAL SQUAD")
    print("-" * 92)
    print(f"Cost              : £{preferred['cost'] / 10:.1f}m")
    print(f"In bank           : £{(BUDGET - preferred['cost']) / 10:.1f}m")
    print(f"Projection        : {preferred['score']:.2f}")
    print(f"Projection lost   : {preferred['score_lost']:.2f}")
    print(f"Budget saved      : £{preferred['saved'] / 10:.1f}m")

    maximum_ids = {p["id"] for p in maximum_squad}
    preferred_ids = {p["id"] for p in preferred["squad"]}

    removed = [p for p in maximum_squad if p["id"] not in preferred_ids]
    added = [p for p in preferred["squad"] if p["id"] not in maximum_ids]

    if removed or added:
        print()
        print("SQUAD CHANGES")
        print("-" * 92)

        for p in removed:
            print(
                f"OUT  {p['name']:18} "
                f"{p['position']:3} "
                f"£{p['price']:4.1f}m"
            )

        for p in added:
            print(
                f"IN   {p['name']:18} "
                f"{p['position']:3} "
                f"£{p['price']:4.1f}m"
            )

    return results


def compare_formations(players):

    formations = [
        (5, 4, 1),
        (5, 3, 2),
        (4, 5, 1),
        (4, 4, 2),
        (4, 3, 3),
        (3, 5, 2),
        (3, 4, 3),
    ]

    results = []

    for formation in formations:

        squad = optimise_squad(
            players,
            force_formation=formation,
        )

        score = calculate_objective_score(
            squad
        )

        results.append(
            (
                formation,
                score,
                squad,
            )
        )

    results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print()
    print("=" * 92)
    print("FORMATION COMPARISON")
    print("=" * 92)

    best_score = results[0][1]

    for formation, score, squad in results:

        formation_name = "-".join(
            str(value)
            for value in formation
        )

        difference = (
            score - best_score
        )

        captain = next(
            p
            for p in squad
            if p["captain"]
        )

        print(
            f"{formation_name:7} "
            f"{score:6.2f} "
            f"{difference:+6.2f}   "
            f"Captain: "
            f"{captain['name']}"
        )

def compare_squads(base_squad, forced_squad, forced_player):

    base_score = calculate_objective_score(base_squad)
    forced_score = calculate_objective_score(forced_squad)

    base_ids = {
        p["id"]
        for p in base_squad
    }

    forced_ids = {
        p["id"]
        for p in forced_squad
    }

    added = [
        p
        for p in forced_squad
        if p["id"] not in base_ids
    ]

    removed = [
        p
        for p in base_squad
        if p["id"] not in forced_ids
    ]

    print()
    print("-" * 92)
    print(
        f"COMPARISON: FORCE {forced_player['name'].upper()} INTO SQUAD"
    )
    print("-" * 92)

    print(
        f"Normal squad score : {base_score:.2f}"
    )

    print(
        f"Forced squad score : {forced_score:.2f}"
    )

    difference = forced_score - base_score

    print(
        f"Difference         : {difference:+.2f}"
    )

    print()
    print("PLAYERS ADDED")
    print("-" * 50)

    for p in added:
        starter = "START" if p["starter"] else "BENCH"
        marker = ""
        
        if p["captain"]:
            marker = " (C)"
        elif p.get("vice_captain"):
            marker = " (VC)"

        print(
            f"{p['name']:18} "
            f"{p['position']:3} "
            f"£{p['price']:4.1f}m "
            f"{starter:5} "
            f"{marker} "
        )

    print()
    print("PLAYERS REMOVED")
    print("-" * 50)

    for p in removed:
        starter = "START" if p["starter"] else "BENCH"
        captain = " (C)" if p["captain"] else ""

        print(
            f"{p['name']:18} "
            f"{p['position']:3} "
            f"£{p['price']:4.1f}m "
            f"{starter:5}"
            f"{captain}"
        )

    print()

    if difference > 0.01:

        print(
            f"RESULT: Including {forced_player['name']} "
            f"improves the model by {difference:.2f}."
        )

    elif difference < -0.01:

        print(
            f"RESULT: Including {forced_player['name']} "
            f"reduces the model by {abs(difference):.2f}."
        )

    else:

        print(
            "RESULT: The two squad structures are essentially equal."
        )

def print_squad(squad):

    position_order = {
        "GKP": 1,
        "DEF": 2,
        "MID": 3,
        "FWD": 4,
    }

    starters = [
        p for p in squad
        if p["starter"]
    ]

    bench = [
        p for p in squad
        if not p["starter"]
    ]

    starters.sort(
        key=lambda p: (
            position_order[p["position"]],
            -p["rating"]
        )
    )

    bench_goalkeepers = [
        p
        for p in bench
        if p["position"] == "GKP"
    ]

    bench_outfield = [
        p
        for p in bench
        if p["position"] != "GKP"
    ]

    bench_outfield.sort(
        key=lambda p: p["proj_next"],
        reverse=True
    )

    total_cost = sum(
        p["cost"]
        for p in squad
    )

    print()
    print("=" * 92)
    print("                         FPL OPTIMISED TEAM")
    print("=" * 92)

    print()
    print("STARTING XI")
    print("-" * 92)

    current_position = None

    for p in starters:

        if p["position"] != current_position:
            current_position = p["position"]

            names = {
                "GKP": "GOALKEEPER",
                "DEF": "DEFENDERS",
                "MID": "MIDFIELDERS",
                "FWD": "FORWARDS",
            }

            print()
            print(names[current_position])

        captain_marker = ""

        if p["captain"]:
            captain_marker = "  (C)"
        elif p.get("vice_captain"):
            captain_marker = "  (VC)"

        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"£{p['price']:4.1f}m   "
            f"EP {p['ep_next']:4.1f}   "
            f"PPG {p['points_per_game']:4.1f}   "
            f"xGI90 {p['xgi90']:4.2f}   "
            f"FIX {p['fixture_score']:4.1f}   "
            f"Owned {p['ownership']:5.1f}%   "
            f"GW{p['planning_gameweek']} "
            f"{p['proj_next']:4.2f}   "
            f"5GW {p['proj_5gw']:5.2f}   "
            f"{captain_marker}"
        )

    print()
    print("BENCH")
    print("-" * 92)

    for number, p in enumerate(
        bench_outfield,
        start=1
    ):

        print(
            f"{number}. "
            f"{p['name']:16} "
            f"{p['team']:18} "
            f"{p['position']:3} "
            f"£{p['price']:4.1f}m   "
            f"EP {p['ep_next']:4.1f}   "
            f"GW{p['planning_gameweek']} "
            f"{p['proj_next']:4.2f}   "
            f"5GW {p['proj_5gw']:5.2f}"
        )

    for p in bench_goalkeepers:

        print(
            f"   GK "
            f"{p['name']:13} "
            f"{p['team']:18} "
            f"£{p['price']:4.1f}m   "
            f"EP {p['ep_next']:4.1f}   "
            f"GW{p['planning_gameweek']} "
            f"{p['proj_next']:4.2f}   "
            f"5GW {p['proj_5gw']:5.2f}"
        )

    captain_player = next(
        p for p in squad
        if p["captain"]
    )

    vice_captain_player = next(
        p
        for p in squad
        if p.get("vice_captain")
    )

    print()
    print("=" * 92)
    print(
        f"Captain    : "
        f"{captain_player['name']} "
        f"({captain_player['team']})"
    )
    print(
        f"Vice       : "
        f"{vice_captain_player['name']} "
        f"({vice_captain_player['team']})"
    )
    print(
        f"Squad cost : "
        f"£{total_cost / 10:.1f}m"
    )
    print(
        f"In bank    : "
        f"£{(BUDGET - total_cost) / 10:.1f}m"
    )
    print("=" * 92)

def print_projection_table(players, names):

    projection_gws = sorted(
        {
            int(key.replace("proj_gw", ""))
            for p in players
            for key in p
            if key.startswith("proj_gw")
            and key != "proj_5gw"
        }
    )

    wanted = [
        p
        for p in players
        if p["name"] in names
    ]

    wanted.sort(
        key=lambda p: p["proj_5gw"],
        reverse=True
    )

    print()

    print(
        f"GW{projection_gws[0]}-"
        f"GW{projection_gws[-1]} PROJECTIONS"
    )

    print("-" * 88)

    header = (
        f"{'Player':18} "
        f"{'Price':>7} "
    )

    for gw in projection_gws:
        header += (
            f"{'GW' + str(gw):>7} "
        )

    header += f"{'Total':>7}"

    print(header)

    print("-" * 88)

    for p in wanted:

        line = (
            f"{p['name']:18} "
            f"£{p['price']:5.1f} "
        )

        for gw in projection_gws:

            line += (
                f"{p.get(f'proj_gw{gw}', 0.0):7.2f} "
            )

        line += (
            f"{p.get('proj_5gw', 0.0):7.2f}"
        )

        print(line)

def print_projection_debug(players, names):

    planning_gameweek = players[0]["planning_gameweek"]

    print()
    print("PROJECTION DEBUG")
    print("-" * 100)

    print(
        f"{'Player':18} "
        f"{'PPG':>5} "
        f"{'EP':>5} "
        f"{'Rel':>5} "
        f"{'Hist':>6} "
        f"{'Under':>7} "
        f"{'Base':>6} "
        f"{'GW' + str(planning_gameweek):>6}"
    )

    print("-" * 100)

    for p in players:

        if p["name"] not in names:
            continue

        d = p["projection_debug"]

        print(
            f"{p['name']:18} "
            f"{d['ppg']:5.2f} "
            f"{d['ep_next']:5.2f} "
            f"{d['reliability']:5.2f} "
            f"{d['historical_baseline']:6.2f} "
            f"{d['underlying_adjustment']:7.2f} "
            f"{d['projected_baseline']:6.2f} "
            f"{p['proj_next']:6.2f}"
        )


def print_goalkeeper_diagnostic(players, names):

    planning_gameweek = players[0]["planning_gameweek"]

    print()
    print("GOALKEEPER DIAGNOSTIC")
    print("-" * 110)

    print(
        f"{'Player':18} "
        f"{'Team':18} "
        f"{'Price':>6} "
        f"{'Min':>5} "
        f"{'Starts':>6} "
        f"{'Status':>7} "
        f"{'Chance':>7} "
        f"{'GW' + str(planning_gameweek):>6} "
        f"{'5GW':>6} "
        f"{'Start%':>7} "
    )

    print("-" * 110)

    for p in players:

        if p["name"] not in names:
            continue

        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"£{p['price']:4.1f}m "
            f"{p['minutes']:5} "
            f"{p['starts']:6} "
            f"{p['status']:>7} "
            f"{str(p.get('chance_of_playing_next_round')):>7} "
            f"{p['proj_next']:6.2f} "
            f"{p['proj_5gw']:6.2f} "
            f"{p['projection_debug']['expected_start_probability'] * 100:6.0f}% "
        )

def print_playing_time_debug(
    players,
    names,
):

    print()
    print("PLAYING TIME DEBUG")
    print("-" * 100)

    print(
        f"{'Player':18} "
        f"{'Team':18} "
        f"{'Pos':>3} "
        f"{'FPL':>5} "
        f"{'Chance':>7} "
        f"{'Start%':>7} "
        f"{'RW Pos':>6} "
        f"{'RW':>5}"
    )

    print("-" * 100)

    for p in players:

        if p["name"] not in names:
            continue

        d = p["projection_debug"]

        chance = (
            p.get(
                "chance_of_playing_next_round"
            )
        )

        rw_group = (
            p.get("rotowire_group")
            or "-"
        )

        rw_status = (
            p.get("rotowire_status")
            or "-"
        )

        print(
            f"{p['name']:18} "
            f"{p['team']:18} "
            f"{p['position']:>3} "
            f"{p['status']:>5} "
            f"{str(chance):>7} "
            f"{d['expected_start_probability'] * 100:6.0f}% "
            f"{rw_group:>6} "
            f"{rw_status:>5}"
        )


if __name__ == "__main__":

    print("Downloading live FPL data...")

    print(
        "FPL UNCONSTRAINED / WILDCARD BENCHMARK"
    )

    players = load_players()

    #
    # Debug-only output
    #
    if DEBUG:

        print_goalkeeper_diagnostic(
            players,
            {
                "Raya",
                "Kinsky",
                "Martinez",
                "Verbruggen",
                "Dubravka",
            }
        )

        print_playing_time_debug(
            players,
            [
                "Bruno G.",
                "Gakpo",
                "Haaland",
                "Richarlison",
                "Dewsbury-Hall",
                "Wilson",
                "Gabriel",
                "Guéhi",
                "Muñoz",
            ],
        )

        print_projection_debug(
            players,
            {
                "Haaland",
                "B.Fernandes",
                "Gabriel",
            }
        )

    #
    # Useful normal output
    #
    print_projection_table(
        players,
        {
            "Haaland",
            "B.Fernandes",
            "Saka",
            "Palmer",
            "Mbeumo",
            "Cherki",
            "João Pedro",
            "Thiago",
            "Gabriel",
            "Raya",
        }
    )

    print(
        f"Considering {len(players)} selectable players..."
    )

    #
    # Normal optimisation
    #
    squad = optimise_squad(players)

    print_squad(squad)

    analyse_budget_efficiency(
        players,
        squad,
    )

    #
    # Premium player comparisons
    #
    comparison_players = [
        ("Haaland", "Man City"),
        ("Saka", "Arsenal"),
        ("Palmer", "Chelsea"),
    ]

    for player_name, team_name in comparison_players:

        comparison_player = next(
            (
                p
                for p in players
                if p["name"] == player_name
                and p["team"] == team_name
            ),
            None
        )

        if comparison_player is None:
            continue

        already_selected = any(
            p["id"] == comparison_player["id"]
            for p in squad
        )

        print()
        print("=" * 92)

        if already_selected:

            print(
                f"{comparison_player['name']} is already "
                f"in the optimal squad."
            )

            continue

        alternative_squad = optimise_squad(
            players,
            force_player_id=comparison_player["id"]
        )

        print()
        print(
            f"{comparison_player['name'].upper()} ALTERNATIVE"
        )

        print_squad(alternative_squad)

        compare_squads(
            squad,
            alternative_squad,
            comparison_player
        )

        compare_formations(players)

