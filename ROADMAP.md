# Busy Working FPL Assistant — Roadmap

This roadmap tracks the current state, immediate priorities and longer-term direction of the FPL assistant.

The guiding principle is to improve the quality of real weekly FPL decisions rather than add complexity for its own sake. Priorities may change when a live gameweek exposes a more important weakness in the model.

## Current — Working Now

The assistant currently supports:

- Live official FPL player, team and fixture data.
- Authenticated retrieval of the current FPL squad.
- Rolling multi-gameweek player projections.
- Fixture difficulty and team-strength adjustments.
- Early-season shrinkage to reduce overreaction to small samples.
- Fresh 15-player squad optimisation under FPL constraints.
- Current-squad optimisation for HOLD, one-transfer and multi-transfer paths.
- Actual selling prices and available bank.
- Free-transfer and transfer-hit accounting.
- Legal starting-XI and bench selection.
- Captain and vice-captain selection.
- Formation comparison diagnostics.
- Goalkeeper playing-time confidence using RotoWire depth information.
- RotoWire outfield availability context (`GTD`, `OUT`, `SUS`).
- Official FPL availability percentages as the primary signal where supplied.
- A minimum free-transfer gain threshold so tiny numerical improvements do not automatically consume a transfer.
- Season benchmark history in `data/season_history.csv`.

## Next — Budget Efficiency

### Goal

Stop treating every available £0.1m as something that should necessarily be spent.

The highest projected squad may cost £100.0m while a squad costing several million less could be almost indistinguishable in expected points. Preserving that money can create valuable future transfer flexibility.

### Planned work

- Calculate the maximum projected squad score.
- Find cheaper squads within a small tolerance of that optimum.
- Report the marginal projected-points cost of keeping money in the bank.
- Compare maximum-score and near-optimal/value squads.
- Consider whether bank value should become part of transfer recommendations.

Example:

```text
Maximum projection:
£100.0m -> 71.68

Near-optimal:
£97.5m -> 71.51

Saving £2.5m costs only 0.17 projected points.
```

The cheaper squad may be strategically preferable even though it is not the mathematical maximum for the current projection window.

## Near Term

### 1. Smarter Free-Transfer Valuation

Improve the current fixed minimum projected-gain threshold using factors such as the number of free transfers available, value of rolling, injury/suspension, expected loss of a starting place, replacement quality, fixture swings, payback period and price changes.

Ultimately the model should value the future option created by rolling rather than relying solely on a fixed threshold.

### 2. Outfield Playing-Time Confidence

Current limitation: an outfield player without explicit availability information effectively receives 100% expected-start probability.

RotoWire's flat outfield lists cannot safely be interpreted as starting-XI rankings, so playing-time confidence needs its own model.

Potential inputs include recent starts/minutes, substitution patterns, FPL minutes, injury/team news, rotation risk and European/cup fixture congestion.

Keep **availability** and **expected start probability** as separate concepts.

### 3. Projection Validation

Use accumulated gameweek data to compare projected and actual FPL points.

Analyse error by position, player price, team, home/away, fixture difficulty, captaincy and expected playing time. Look for systematic biases and use evidence from the season to recalibrate the model.

### 4. Multi-Gameweek Transfer Planning

Move from “What is the best move this week?” towards “What is the best transfer strategy over the next few gameweeks?”

Compare rolling and future two-transfer paths against acting immediately, including future free transfers, hits, bank, selling prices, fixture swings and expected squad value.

This should eventually replace part of the heuristic free-transfer threshold.

## Later

### Captaincy Improvements

Review captain selection using ceiling/upside, goal involvement, penalties, opponent defensive strength, home advantage and expected minutes. Potentially report model, safe and high-upside captain options.

### Price-Change Awareness

Investigate expected FPL price changes to warn about likely rises/falls and quantify team-value consequences. Price movement should inform a decision rather than automatically trigger one.

### Chips and Special Gameweeks

Add explicit planning for Wildcard, Free Hit, Bench Boost, Triple Captain, blank gameweeks, double gameweeks and rearranged fixtures.

### Weekly Decision Report

Create a concise decision-focused output while retaining detailed optimiser output as a diagnostic mode.

Example:

```text
GW8 RECOMMENDATION

Transfer: ROLL
Best optional move: Player A -> Player B (+0.63)

Captain: Haaland
Vice: Saka

Key concerns:
Player X - 75% chance
Player Y - rotation risk

Bank: £1.5m
Free transfers next GW: 2
```

### Web Dashboard

Once recommendations are sufficiently trusted, build a lightweight Raspberry Pi web interface with possible views for This Gameweek, My Squad, Transfers, Player Comparison, Fixture Planner, Season Performance and Model Diagnostics.

The terminal tools should remain independently usable.

## Technical / Maintenance Backlog

- Add automated tests for projection and transfer logic.
- Cache external data where appropriate.
- Handle external-source failures gracefully.
- Continue improving player/team name matching.
- Replace temporary debug output with structured logging where useful.
- Remove obsolete diagnostic scripts.
- Keep secrets and refresh tokens outside Git.
- Keep Mac development and Raspberry Pi runtime environments reproducible.
- Keep README and roadmap aligned with implemented behaviour.

### Rename Project / Repository

The current `busy-working-fpl-assistant` name was inherited from the
"Busy Working" Fantasy NFL project and is unrelated to this FPL assistant.

Choose a clearer project name and rename the GitHub repository once the
main modelling work is stable.

Before renaming:

- Search the codebase for references to `busy-working-fpl-assistant`.
- Check local paths on the Mac and Raspberry Pi.
- Check Git remote URLs on both machines.
- Check scripts, documentation and configuration for hard-coded paths.
- Rename the GitHub repository.
- Update local Git remotes.
- Optionally rename the local project directories.
- Update README/documentation.
- Test the normal Mac -> GitHub -> Raspberry Pi workflow.

The rename should be treated as a maintenance change rather than combined
with modelling changes.

## Completed Milestones

Recent completed work includes:

- Formation comparison diagnostic.
- Early-season projection improvements.
- Goalkeeper depth-chart integration.
- Outfield RotoWire matching and availability integration.
- FPL-first availability handling to avoid double penalties.
- Season benchmark history.
- Transfer recommendation threshold separating the best available transfer from a transfer worth making.

## Priority Order

1. **Budget efficiency** — next.
2. Smarter free-transfer valuation.
3. Outfield playing-time confidence.
4. Projection validation.
5. Multi-gameweek transfer planning.

The order is intentionally flexible: a live gameweek decision can promote an issue if it reveals a material weakness in the model.
