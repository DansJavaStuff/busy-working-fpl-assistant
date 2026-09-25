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

LATER MILESTONE — HOSTED WEEKLY MANAGER

[x] Build local Flask dashboard
[x] Display current FPL squad
[x] Display transfer scenarios
[x] Display recommended transfers
[x] Show proposed XI / bench / captain
[x] Add Approve / Reject workflow
[x] Add dry-run FPL write layer
[x] Test team-selection API write
[x] Test transfer API write
[ ] Add authentication
[ ] Add scheduled Friday optimiser run
[ ] Deploy to hosted service

The local dashboard is now the main interactive surface. It also includes Gameweek history, first-run local setup and a read-only chip planner. Hosted deployment remains deliberately deferred while the decision model is improved.

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

### Budget-efficiency follow-up

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

## Current — Chip Schedule & Historical Intelligence

Before moving on to transfer valuation, turn the chip opportunity model into a coordinated, confidence-aware schedule.

- [x] Historical data foundation: versioned local SQLite store
- [x] Rebuildable schema migrations
- [x] Separate runtime data from Git-tracked code/reference data
- [x] Add persistent SQLite caching for expensive chip calculations
- [x] Invalidate cached chip analysis by squad / transfer / chip state and model version
- [ ] Extend persistent derived-result caching to other expensive model pages where useful
- [x] Save append-only pre-deadline weekly snapshots
- [x] Capture baseline plus T-60m / T-15m / T-10m / T-5m checkpoints
- [x] Require fresh official public FPL data for deadline checkpoints
- [x] Recover checkpoint captures after short Pi outages and record lateness
- [x] Show snapshot collector health and checkpoint status on Gameweek HQ
- [x] Compare consecutive snapshots for material/dependency changes
- [ ] Review checkpoint value after 4–5 complete Gameweeks and simplify T−15m / T−10m / T−5m if evidence shows they are redundant
- [ ] Extend snapshot comparison to answer whether the optimiser/chip recommendation would actually have changed
- [x] Import historical fixture / Gameweek context
- [x] Pin historical imports to an upstream source commit for reproducibility
- [x] Reconstruct historical blank / double Gameweek structure from imported fixtures
- [ ] Build full GW-by-GW value curves for all four chips
- [ ] Add fixture-certainty and model-confidence signals
- [ ] Allow explicit HOLD / insufficient-data recommendations
- [ ] Build coordinated chip schedule with one-chip-per-GW constraints
- [ ] Backtest historical chip patterns and outcomes
- [ ] Explain useful historical analogues without overfitting to Gameweek number

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
- [x] Add initial automated tests for chip-planner logic
- [x] Add GitHub Actions CI for compile, tests and lightweight linting
- [x] Add runtime / development dependency manifests
- [x] Add dependency vulnerability audit to CI
- [x] Configure weekly Dependabot dependency updates
- [x] Add first-run local setup for FPL Entry ID and refresh token
- [x] Remove hard-coded personal FPL Entry ID from application code
- [x] Add protected-main ruleset once CI check names are confirmed
- [x] Expand automated tests for chip-planner logic
- [ ] Cache external data where appropriate
- [ ] Handle external-source failures gracefully
- [ ] Continue improving player / team name matching
- [ ] Replace temporary debug output with structured logging where useful
- [ ] Remove obsolete diagnostic scripts
- [x] Keep secrets and refresh tokens outside Git
- [x] Keep Mac development and Raspberry Pi runtime environments reproducible
- [x] Keep README and roadmap aligned with implemented behaviour

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

### Chip Planner Hardening and Special Gameweeks

Completed in September 2026. The four standard chips have scored planning models, half-season-aware timing, explicit rule-boundary validation, and special-Gameweek-aware projections.

2026/27 official FPL mechanics that the planner must preserve:

- Two sets of Wildcard, Free Hit, Bench Boost and Triple Captain: one set for GW1–19 and a refreshed set from GW20 onward
- First-half chips expire after GW19 and do not carry over
- Only one chip can be played in a Gameweek
- Wildcard and Free Hit preserve banked free transfers
- Free Hit cannot be played in GW1 and cannot be played in both GW19 and GW20
- Wildcard cannot be played in GW1
- Bench Boost scores all 15 squad players
- Triple Captain triples the captain's score rather than doubling it
- Free Hit changes are temporary; Wildcard changes are permanent

Implemented:

- [x] Wildcard planning
- [x] Free Hit planning
- [x] Bench Boost planning
- [x] Triple Captain planning
- [x] First-half future timing windows through GW19
- [x] Cross-chip opportunity-cost comparison
- [x] Lazy-loaded / cached opportunity analysis
- [x] Reuse normal optimiser scenarios to reduce duplicate chip computation

Hardening:

- [x] Add automated chip-planner regression tests
- [x] Encode / validate chip availability boundary rules explicitly
- [x] Verify opportunity scoring against representative timing scenarios
- [x] Ensure GW19 -> GW20 refresh behaviour is handled correctly
- [x] Keep long-range timing estimates clearly separate from current fixture assignments

Special-Gameweek mechanics:

- [x] Blank-gameweek planning
- [x] Double-gameweek planning
- [x] Rearranged-fixture handling through FPL Gameweek assignment
- [x] Make Free Hit timing explicitly sensitive to blank Gameweeks
- [x] Make Bench Boost / Triple Captain timing explicitly sensitive to double Gameweeks


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

1. **Chip schedule & historical intelligence** — current modelling priority.
2. Smarter free-transfer valuation.
3. Outfield playing-time confidence.
4. Projection validation.
5. Multi-gameweek transfer planning.
6. Captaincy improvements.
7. Price-change awareness.
8. Weekly decision report.
9. Hosted-service work: authentication, scheduling and deployment.
10. Project rename and technical cleanup.

Budget-efficiency work can continue as a refinement alongside the current transfer-valuation work; it does not block the next modelling milestone.

The order is intentionally flexible: a live gameweek decision can promote an issue if it reveals a material weakness in the model.

## Development Principle

The assistant should improve real weekly FPL decisions and save time.

It should not add complexity merely because another feature is technically possible.
