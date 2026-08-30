# Busy Working FPL Assistant — Roadmap

A personal Fantasy Premier League assistant that combines official FPL data
with external context to help with squad selection, transfers, captaincy and
longer-term planning.

## Current State

The assistant can currently:

- Download live official FPL player, team and fixture data.
- Authenticate against the user's FPL account and retrieve the current squad.
- Model expected player points over upcoming gameweeks.
- Apply fixture difficulty and team-strength adjustments.
- Reduce early-season reliance on small current-season samples.
- Optimise a fresh 15-player squad within FPL constraints.
- Optimise the current squad for:
  - Hold / no transfer
  - 1 transfer
  - 2 transfers
  - 3 transfers
- Account for:
  - Available bank
  - Actual player selling prices
  - Free transfers
  - Transfer hit costs
- Select the best legal starting XI and bench.
- Recommend captain and vice-captain.
- Compare common FPL formations as a diagnostic.
- Use RotoWire depth-chart information for goalkeeper playing-time confidence.
- Use RotoWire outfield information as a secondary availability source.
- Prefer explicit FPL availability percentages when available, avoiding
  duplicate availability penalties.
- Track current squad, best transfer path and ideal fresh-squad scores in
  `data/season_history.csv`.
- Preserve a free transfer when the best available move does not exceed the
  minimum transfer-gain threshold.

---

# Development Roadmap

## 1. Budget Efficiency

### Goal

Stop treating every available £0.1m as something that should necessarily be
spent.

### Work

- Calculate the maximum projected squad score.
- Find cheaper squads within a small tolerance of that optimum.
- Report the cost of gaining the final fractions of a projected point.
- Consider assigning value to money left in the bank.
- Preserve budget flexibility where spending more provides negligible benefit.

Example:

    Maximum projection:
    £100.0m -> 71.68

    Near-optimal:
    £97.5m -> 71.51

    Saving £2.5m costs only 0.17 projected points.

This could make the cheaper squad strategically preferable.

---

## 2. Smarter Free-Transfer Valuation

### Current implementation

A free transfer is currently only recommended when the best transfer path
beats HOLD by at least:

    MINIMUM_FREE_TRANSFER_GAIN = 1.0

### Improvements

Replace the fixed threshold with a more intelligent model.

Potential factors:

- Number of free transfers currently available.
- Ability to roll another transfer.
- Injury or suspension.
- Player expected to lose their starting place.
- Strength of the replacement.
- Upcoming fixture swing.
- Number of gameweeks over which the transfer pays back.
- Price rises/falls where relevant.

The model should distinguish between:

    Best available transfer

and:

    Transfer worth making

---

## 3. Outfield Playing-Time Confidence

### Current limitation

Outfield players without explicit availability information effectively receive
100% expected-start probability.

RotoWire currently provides useful status information such as:

- GTD
- OUT
- SUS

but its flat outfield depth-chart ordering cannot safely be interpreted as a
starting-XI ranking.

### Work

Develop a separate estimate for:

    expected_start_probability

Possible inputs:

- Recent starts.
- Recent minutes.
- Substitution patterns.
- FPL minutes.
- Injury/availability information.
- External team-news/depth information.
- Rotation risk.
- European/cup schedule congestion.

Keep this separate from general player availability.

---

## 4. Projection Validation

### Goal

Determine whether the model actually predicts FPL points well.

Use accumulated gameweek data to compare:

    projected points
    vs
    actual points

Analyse errors by:

- Position.
- Player price.
- Team.
- Home/away.
- Fixture difficulty.
- Captaincy.
- Expected playing time.

Look for systematic biases such as:

- Overrating defenders.
- Underrating premium attackers.
- Excessive fixture weighting.
- Excessive recent-form weighting.

Use the results to recalibrate the projection model.

---

## 5. Multi-Gameweek Transfer Planning

### Goal

Move from:

    What is the best move this week?

towards:

    What is the best transfer strategy over the next few gameweeks?

Model possible paths such as:

    GW2: Roll
    GW3: Use 2 FT
    GW4: Roll

versus:

    GW2: Transfer A -> B
    GW3: Transfer C -> D

Include:

- Future free transfers.
- Hits.
- Bank.
- Selling prices.
- Fixture swings.
- Expected squad value.

This should eventually replace some of the heuristic free-transfer threshold.

---

## 6. Captaincy Improvements

Review captain selection as more data becomes available.

Potential improvements:

- Ceiling/upside rather than expected points alone.
- Player goal involvement.
- Penalty-taking status.
- Opponent defensive strength.
- Home advantage.
- Expected minutes.
- Captaincy uncertainty.

Consider reporting:

    Safe captain
    High-upside captain
    Model captain

where useful.

---

## 7. Price-Change Awareness

Investigate incorporating expected FPL price changes.

Potential uses:

- Warn when a planned target may rise before the next deadline.
- Warn when an owned player is likely to fall.
- Include team-value consequences when comparing otherwise similar transfers.

Price changes should inform decisions rather than automatically trigger
transfers.

---

## 8. Chips and Special Gameweeks

Future support for:

- Wildcard.
- Free Hit.
- Bench Boost.
- Triple Captain.

Later in the season add awareness of:

- Blank gameweeks.
- Double gameweeks.
- Rearranged fixtures.

---

## 9. Weekly Decision Report

Produce one concise output designed for the actual FPL decision.

Example:

    GW8 RECOMMENDATION

    Transfer:
    ROLL

    Best optional move:
    Player A -> Player B (+0.63)

    Starting XI:
    ...

    Captain:
    Haaland

    Vice Captain:
    Saka

    Key concerns:
    Bruno Fernandes - 75% chance
    Player X - rotation risk

    Bank:
    £1.5m

    Free transfers next GW:
    2

Keep detailed optimiser output available as a diagnostic mode.

---

## 10. Web Dashboard

Once the underlying recommendations are trusted, build a lightweight web
interface suitable for hosting on the Raspberry Pi.

Possible pages:

- This Gameweek
- My Squad
- Transfers
- Player Comparison
- Fixture Planner
- Season Performance
- Model Diagnostics

The terminal tools should remain usable independently of the web interface.

---

# Maintenance / Technical Improvements

- Improve README documentation.
- Remove obsolete diagnostic scripts.
- Add automated tests for projection and transfer logic.
- Cache external data where appropriate.
- Handle external-source failures gracefully.
- Improve player/team name matching.
- Add logging rather than temporary debug prints.
- Keep secrets and refresh tokens outside Git.
- Keep Mac development and Raspberry Pi runtime environments reproducible.

---

# Current Priority

**Next: Budget Efficiency**

After that:

1. Smarter free-transfer valuation.
2. Outfield playing-time confidence.
3. Projection validation.
4. Multi-gameweek transfer planning.

The priority may change during the season when an immediate FPL decision
reveals a more important weakness in the model.
