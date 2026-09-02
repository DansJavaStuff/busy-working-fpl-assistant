from pathlib import Path
import sys

path = Path('optimizer.py')
backup = Path('optimizer.py.before-budget-efficiency')

if not path.exists():
    sys.exit('ERROR: optimizer.py not found. Run this from the project directory.')

text = path.read_text(encoding='utf-8')

if 'def analyse_budget_efficiency(' in text:
    sys.exit('Budget-efficiency code already appears to be installed.')

backup.write_text(text, encoding='utf-8')

old_signature = '''def optimise_squad(\n    players, \n    force_player_id=None, \n    force_formation=None,\n):\n\n    problem = pulp.LpProblem(\n        "FPL_Squad",\n        pulp.LpMaximize\n    )\n'''

new_signature = '''def optimise_squad(\n    players,\n    force_player_id=None,\n    force_formation=None,\n    minimum_objective_score=None,\n    minimise_cost=False,\n):\n\n    problem = pulp.LpProblem(\n        "FPL_Squad",\n        (\n            pulp.LpMinimize\n            if minimise_cost\n            else pulp.LpMaximize\n        )\n    )\n'''

if old_signature not in text:
    sys.exit('ERROR: Could not find the expected optimise_squad() header. No changes were made.')
text = text.replace(old_signature, new_signature, 1)

old_objective = '''    problem += pulp.lpSum(\n        (\n            starter[p["id"]] * p["proj_next"]\n            +\n            captain[p["id"]] * calculate_captain_score(p)\n            +\n            selected[p["id"]]\n            * p["proj_5gw"]\n            * SQUAD_HORIZON_WEIGHT\n        )\n        for p in players\n    )\n    \n    #\n    # SQUAD RULES\n'''

new_objective = '''    projection_objective = pulp.lpSum(\n        (\n            starter[p["id"]] * p["proj_next"]\n            +\n            captain[p["id"]] * calculate_captain_score(p)\n            +\n            selected[p["id"]]\n            * p["proj_5gw"]\n            * SQUAD_HORIZON_WEIGHT\n        )\n        for p in players\n    )\n\n    squad_cost = pulp.lpSum(\n        selected[p["id"]] * p["cost"]\n        for p in players\n    )\n\n    if minimise_cost:\n        problem += squad_cost\n    else:\n        problem += projection_objective\n\n    if minimum_objective_score is not None:\n        problem += (\n            projection_objective\n            >= minimum_objective_score\n        )\n    \n    #\n    # SQUAD RULES\n'''

if old_objective not in text:
    sys.exit('ERROR: Could not find the optimisation objective block. No changes were written.')
text = text.replace(old_objective, new_objective, 1)

old_budget = '''    problem += pulp.lpSum(\n        selected[p["id"]] * p["cost"]\n        for p in players\n    ) <= BUDGET\n'''
new_budget = '''    problem += squad_cost <= BUDGET\n'''

if old_budget not in text:
    sys.exit('ERROR: Could not find the budget constraint. No changes were written.')
text = text.replace(old_budget, new_budget, 1)

marker = 'def compare_formations(players):\n'

budget_function = '''def analyse_budget_efficiency(\n    players,\n    maximum_squad,\n    tolerances=(0.10, 0.25, 0.50, 1.00),\n):\n    """Find the cheapest legal squad within each score tolerance."""\n\n    maximum_score = calculate_objective_score(maximum_squad)\n    maximum_cost = sum(p["cost"] for p in maximum_squad)\n    results = []\n\n    for tolerance in tolerances:\n        minimum_score = maximum_score - tolerance\n        value_squad = optimise_squad(\n            players,\n            minimum_objective_score=minimum_score,\n            minimise_cost=True,\n        )\n        value_score = calculate_objective_score(value_squad)\n        value_cost = sum(p["cost"] for p in value_squad)\n\n        results.append({\n            "tolerance": tolerance,\n            "squad": value_squad,\n            "score": value_score,\n            "cost": value_cost,\n            "saved": maximum_cost - value_cost,\n            "score_lost": maximum_score - value_score,\n        })\n\n    print()\n    print("=" * 92)\n    print("BUDGET EFFICIENCY")\n    print("=" * 92)\n    print(\n        f"Maximum projection : £{maximum_cost / 10:.1f}m "\n        f"-> {maximum_score:.2f}"\n    )\n\n    print()\n    print(\n        f"{'Tolerance':>10} "\n        f"{'Cost':>9} "\n        f"{'Bank':>9} "\n        f"{'Score':>9} "\n        f"{'Lost':>9}"\n    )\n    print("-" * 52)\n\n    for result in results:\n        print(\n            f"{result['tolerance']:9.2f} "\n            f"£{result['cost'] / 10:7.1f}m "\n            f"£{(BUDGET - result['cost']) / 10:7.1f}m "\n            f"{result['score']:9.2f} "\n            f"{result['score_lost']:9.2f}"\n        )\n\n    preferred = next(\n        result for result in results\n        if abs(result["tolerance"] - 0.25) < 0.001\n    )\n\n    print()\n    print("0.25-POINT NEAR-OPTIMAL SQUAD")\n    print("-" * 92)\n    print(f"Cost              : £{preferred['cost'] / 10:.1f}m")\n    print(f"In bank           : £{(BUDGET - preferred['cost']) / 10:.1f}m")\n    print(f"Projection        : {preferred['score']:.2f}")\n    print(f"Projection lost   : {preferred['score_lost']:.2f}")\n    print(f"Budget saved      : £{preferred['saved'] / 10:.1f}m")\n\n    maximum_ids = {p["id"] for p in maximum_squad}\n    preferred_ids = {p["id"] for p in preferred["squad"]}\n\n    removed = [p for p in maximum_squad if p["id"] not in preferred_ids]\n    added = [p for p in preferred["squad"] if p["id"] not in maximum_ids]\n\n    if removed or added:\n        print()\n        print("SQUAD CHANGES")\n        print("-" * 92)\n\n        for p in removed:\n            print(\n                f"OUT  {p['name']:18} "\n                f"{p['position']:3} "\n                f"£{p['price']:4.1f}m"\n            )\n\n        for p in added:\n            print(\n                f"IN   {p['name']:18} "\n                f"{p['position']:3} "\n                f"£{p['price']:4.1f}m"\n            )\n\n    return results\n\n\n'''

if marker not in text:
    sys.exit('ERROR: Could not find compare_formations(). No changes were written.')
text = text.replace(marker, budget_function + marker, 1)

old_main = '''    print_squad(squad)\n\n    #\n    # Premium player comparisons\n'''
new_main = '''    print_squad(squad)\n\n    analyse_budget_efficiency(\n        players,\n        squad,\n    )\n\n    #\n    # Premium player comparisons\n'''

if old_main not in text:
    sys.exit('ERROR: Could not find the main output block. No changes were written.')
text = text.replace(old_main, new_main, 1)

path.write_text(text, encoding='utf-8')

print('Budget-efficiency changes applied successfully.')
print(f'Backup saved as: {backup}')
print('Next: python3 -m py_compile optimizer.py')
