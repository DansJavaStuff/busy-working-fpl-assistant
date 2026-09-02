# Fantasy EPL Assistant — Roadmap

This roadmap tracks the current state, immediate priorities and longer-term direction of the Fantasy EPL assistant.

The guiding principle is to improve the quality of real weekly FPL decisions rather than add complexity for its own sake. Priorities may change when a live gameweek exposes a more important weakness in the model.

## Current Status

The assistant currently supports:

- [x] Live official FPL player, team and fixture data
- [x] Authenticated retrieval of the current FPL squad
- [x] Rolling multi-gameweek player projections
- [x] Fixture difficulty and team-strength adjustments
- [x] Early-season shrinkage to reduce overreaction to small samples
- [x] Fresh 15-player squad optimisation under FPL constraints
- [x] Current-squad optimisation for HOLD, one-transfer and multi-transfer paths
- [x] Actual selling prices and available bank
- [x] Free-transfer and transfer-hit accounting
- [x] Legal starting-XI and bench selection
- [x] Captain and vice-captain selection
- [x] Formation comparison diagnostics
- [x] Goalkeeper playing-time confidence using RotoWire depth information
- [x] RotoWire outfield availability context (`GTD`, `OUT`, `SUS`)
- [x] Official FPL availability percentages as the primary signal where supplied
- [x] Minimum free-transfer gain threshold so tiny numerical improvements do not automatically consume a transfer
- [x] Season benchmark history in `data/season_history.csv`

CURRENT MILESTONE — HOSTED WEEKLY MANAGER

[ ] Build local Flask dashboard
[ ] Display current FPL squad
[ ] Display transfer scenarios
[ ] Display recommended transfers
[ ] Show proposed XI / bench / captain
[ ] Add Approve / Reject workflow
[ ] Add dry-run FPL write layer
[ ] Test team-selection API write
[ ] Test transfer API write
[ ] Add authentication
[ ] Add scheduled Friday optimiser run
[ ] Deploy to hosted service

ONGOING — OPTIMISER REFINEMENT

[✓] Previous-season player baselines
[✓] Historical positional priors
[✓] Rolling fixture horizon
[✓] Safer transfer-hit decisions
[ ] Refine early-season projections
[ ] Review captaincy model
[ ] Add price-change awareness
[ ] Improve transfer value / budget flexibility
[ ] Track recommendation accuracy through season

### Goal

Stop treating every available £0.1m as something that should necessarily be spent.

The highest projected squad may cost £100.0m while a squad costing several million less could be almost indistinguishable in expected points. Preserving that money can create valuable future transfer flexibility.

### Now

- [ ] Calculate the maximum projected squad score
- [ ] Find cheaper squads within a small tolerance of that optimum
- [ ] Report the marginal projected-points cost of keeping money in the bank
- [ ] Compare maximum-score and near-optimal / value squads
- [ ] Decide whether bank value should become part of transfer recommendations

Example target output:

Maximum projection:
£100.0m -> 71.68

Near-optimal:
£97.5m -> 71.51

Saving £2.5m costs only 0.17 projected points.

The cheaper squad may be strategically preferable even though it is not the mathematical maximum for the current projection window.

## Next — Smarter Free-Transfer Valuation

Improve the current fixed minimum projected-gain threshold.

- [ ] Account for the number of free transfers available
- [ ] Value the option of rolling a transfer
- [ ] Increase urgency for injury / suspension
- [ ] Increase urgency when a player is expected to lose a starting place
- [ ] Account for replacement quality
- [ ] Account for fixture swings
- [ ] Consider transfer payback period
- [ ] Consider likely price changes
- [ ] Move toward explicit future-option value instead of relying solely on a fixed threshold

## Near Term — Outfield Playing-Time Confidence

Current limitation: an outfield player without explicit availability information effectively receives 100% expected-start probability.

RotoWire's flat outfield lists cannot safely be interpreted as starting-XI rankings, so playing-time confidence needs its own model.

Keep **availability** and **expected start probability** as separate concepts.

Potential work:

- [ ] Use recent starts
- [ ] Use recent minutes
- [ ] Use substitution patterns
- [ ] Use official FPL minutes
- [ ] Use injury / team news
- [ ] Account for rotation risk
- [ ] Account for European / cup fixture congestion
- [ ] Build an explicit outfield expected-start probability

## Near Term — Projection Validation

Use accumulated gameweek data to compare projected and actual FPL points.

- [ ] Compare projected vs actual points overall
- [ ] Analyse error by position
- [ ] Analyse error by player price
- [ ] Analyse error by team
- [ ] Analyse home vs away error
- [ ] Analyse fixture-difficulty error
- [ ] Analyse captaincy error
- [ ] Analyse expected-playing-time error
- [ ] Identify systematic model biases
- [ ] Recalibrate the model using season evidence

## Near Term — Multi-Gameweek Transfer Planning

Move from “What is the best move this week?” toward “What is the best transfer strategy over the next few gameweeks?”

- [ ] Compare acting now against rolling
- [ ] Model future two-transfer paths
- [ ] Include future free transfers
- [ ] Include transfer hits
- [ ] Include bank
- [ ] Include actual selling prices
- [ ] Include fixture swings
- [ ] Include expected squad value
- [ ] Use multi-gameweek planning to replace part of the heuristic free-transfer threshold

## Later — Captaincy Improvements

- [ ] Review captain selection using ceiling / upside
- [ ] Include goal involvement
- [ ] Include penalty-taking role
- [ ] Include opponent defensive strength
- [ ] Include home advantage
- [ ] Include expected minutes
- [ ] Consider reporting model / safe / high-upside captain options

## Later — Price-Change Awareness

- [ ] Investigate expected FPL price changes
- [ ] Warn about likely rises / falls
- [ ] Quantify team-value consequences
- [ ] Ensure price movement informs decisions rather than automatically triggering them

## Later — Chips and Special Gameweeks

- [ ] Wildcard planning
- [ ] Free Hit planning
- [ ] Bench Boost planning
- [ ] Triple Captain planning
- [ ] Blank-gameweek planning
- [ ] Double-gameweek planning
- [ ] Rearranged-fixture handling

## Later — Weekly Decision Report

Create a concise decision-focused output while retaining detailed optimiser output as a diagnostic mode.

- [ ] Build concise weekly recommendation format
- [ ] Report transfer / roll recommendation
- [ ] Report best optional transfer
- [ ] Report captain and vice-captain
- [ ] Report key availability concerns
- [ ] Report bank
- [ ] Report expected free transfers next gameweek

Example target output:

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

## Later — Web Dashboard

Once recommendations are sufficiently trusted, build a lightweight Raspberry Pi web interface.

Potential views:

- [ ] This Gameweek
- [ ] My Squad
- [ ] Transfers
- [ ] Player Comparison
- [ ] Fixture Planner
- [ ] Season Performance
- [ ] Model Diagnostics

The terminal tools should remain independently usable.

## Technical / Maintenance Backlog

- [ ] Add automated tests for projection logic
- [ ] Add automated tests for transfer logic
- [ ] Cache external data where appropriate
- [ ] Handle external-source failures gracefully
- [ ] Continue improving player / team name matching
- [ ] Replace temporary debug output with structured logging where useful
- [ ] Remove obsolete diagnostic scripts
- [ ] Keep secrets and refresh tokens outside Git
- [ ] Keep Mac development and Raspberry Pi runtime environments reproducible
- [ ] Keep README and roadmap aligned with implemented behaviour

### Project Rename

The current `busy-working-fpl-assistant` name was inherited from the Busy Working Fantasy NFL project and is unrelated to this FPL assistant.

Preferred future direction: a clearer EPL-specific project name such as `fantasy-epl-assistant` or a stronger manager-style name if desired.

Treat the rename as a maintenance change rather than combining it with modelling changes.

- [ ] Finalise the new project name
- [ ] Search the codebase for references to `busy-working-fpl-assistant`
- [ ] Check local paths on the Mac
- [ ] Check local paths on the Raspberry Pi
- [ ] Check Git remote URLs on both machines
- [ ] Check scripts / documentation / configuration for hard-coded paths
- [ ] Rename the GitHub repository
- [ ] Update local Git remotes
- [ ] Rename local project directories if desired
- [ ] Update README / documentation
- [ ] Test the normal Mac -> GitHub -> Raspberry Pi workflow

## Completed Milestones

- [x] Formation comparison diagnostic
- [x] Early-season projection improvements
- [x] Goalkeeper depth-chart integration
- [x] Outfield RotoWire matching and availability integration
- [x] FPL-first availability handling to avoid double penalties
- [x] Season benchmark history
- [x] Transfer recommendation threshold separating the best available transfer from a transfer worth making

## Parking Lot

Good ideas that are deliberately not current priorities:

- [ ] More advanced visualisations
- [ ] Additional external data sources
- [ ] Fully automated weekly reporting
- [ ] Public / multi-user deployment
- [ ] Notification / alert workflows
- [ ] Longer-term model performance dashboard

## Priority Order

1. **Budget efficiency** — current.
2. Smarter free-transfer valuation.
3. Outfield playing-time confidence.
4. Projection validation.
5. Multi-gameweek transfer planning.
6. Captaincy improvements.
7. Price-change awareness.
8. Chips and special gameweeks.
9. Weekly decision report.
10. Web dashboard.
11. Project rename and technical cleanup.

The order is intentionally flexible: a live gameweek decision can promote an issue if it reveals a material weakness in the model.

## Development Principle

The assistant should improve real weekly FPL decisions and save time.

It should not add complexity merely because another feature is technically possible.
