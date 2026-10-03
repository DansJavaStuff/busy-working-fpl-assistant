# Current Status

_Last updated: 2026-10-03_

Durable handoff for `DansJavaStuff/busy-working-fpl-assistant`. Read this first in a new conversation and replace stale details when milestones finish.

## Runtime and workflow

- Raspberry Pi; service `fpl-assistant`; CBC `/usr/bin/cbc`.
- Entry ID / refresh token are local configuration; never commit secrets.
- Existing features: chip HOLD recommendations, historical fixture analogues, read-only planner / Why? diagnostics, cache warmer, deadline snapshots T-60/T-15/T-10/T-5.
- User authorises pushes and merges once tests and required CI/security checks are green.
- Keep this file current as part of each meaningful milestone.

## Latest milestone

- Latest merged baseline: PR #47, `7c1c766` — add the handoff file; PR #46, `abe3e9f` — fixture-shape breakdown.
- Current change: blank-only FH ranking stability benchmark, extending the existing leave-one-season-out comparison. Check its PR/merge status before resuming.
- No live FH thresholds, BB metrics or TC metrics change in this milestone.

## Latest supplied historical results

Five seasons: 2021-22 to 2025-26. The latest Pi run took 12m42.8s.

- FH now uses pre-deadline-proxy-selected template and Free Hit squads scored afterwards, allowing negative uplift. It is no longer just the earlier hindsight ceiling.
- FH fixture signal: overall +0.270; blank-only +0.651 (22 cases); mixed blank+double -0.359 (8 cases).
- Blank-only regressed-form LOSO comparison: fixture +0.534, projection +0.342, equal-rank blend +0.562. The small blend improvement needs stability testing.
- Optimiser selection magnifies projection errors: player correlation 0.569 across active players, 0.212 in FH XIs. 8+ projected points averaged 9.01 projected vs 5.50 actual.
- Hybrid player calibration remains HOLD: ranking 0.385 improved, but MAE 15.33 exceeds the simpler position-regression benchmark 13.82.
- BB remains a hindsight bench ceiling: +0.678 overall; mixed +0.945; doubles +0.624.
- TC remains a top-20-owned captainable ceiling: +0.279 overall; mixed +0.443; doubles +0.283.

## Current research decision

Treat blank-only and mixed FH as separate archetypes. Fixture signal is the blank-only baseline; projections are a possible supporting ranking signal. Mixed FH remains uncalibrated / HOLD for fitting with eight cases. Leave BB and TC alone.

The new blank-only benchmark compares the same regressed-form squad outcomes for both ranking methods. Percentiles use other seasons only; the blend has fixed equal weights. Outcomes score choices, never select them.

Report additions:

- Per-season correlation delta and each method's top-ranked Gameweek(s), actual uplift and regret relative to the best observed blank FH week in that season.
- Tied first choices average their realised outcomes; no hindsight tiebreak.
- Equal-season mean top-week regret.
- Season deletions of fixed out-of-fold scores: a sensitivity summary, not a refit or significance test.
- Fixed research gate: at least three informative seasons, positive pooled delta, improvement in a majority of informative seasons, no negative season-deletion delta, and no worse mean top-week regret.
- Verdict RESEARCH CANDIDATE only if all gates pass; otherwise HOLD / fixture-only. Neither verdict promotes a production model.

## Immediate next step

After the benchmark PR is merged, run on the Pi in the usual virtual environment:

```bash
cd ~/busy-working-fpl-assistant
git pull
time python3 -m tools.backtest_historical_chip_outcomes
```

Review **Blank-only FH ranking stability**, especially season deletions, top-week regret and failed gates. Paste that section with the preceding LOSO results. No service restart is required for this offline tool.

The benchmark has not yet been run against the Pi historical database in this workspace. Do not invent its acceptance verdict. Update this file with the new measurements and merged PR/commit after the run.

## Caveats that must survive handoff

Archived fixture / team-strength / FDR fields are not proven exact deadline snapshots. FH selection uses prior-GW ownership and form proxies; season-level LOSO is not chronological walk-forward validation. BB and TC still use hindsight ceilings. These are research diagnostics, not sufficient evidence for retuning live thresholds.

Top-week regret compares only the observed blank weeks in a season, without modelling chip inventory, availability or a real manager's squad and transfer options. Five seasons / 22 cases give limited stability evidence. Gate thresholds are research heuristics, not statistical significance claims.
