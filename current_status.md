# Current Status

_Last updated: 2026-10-03_

This file is the durable handoff for the **Busy Working FPL Assistant**. Keep it short, current, and useful enough that a new ChatGPT conversation can read this file and continue without needing the previous chat history.

## Project

- Repository: `DansJavaStuff/busy-working-fpl-assistant`
- Main runtime: Raspberry Pi
- Service: `fpl-assistant`
- Solver: CBC (`/usr/bin/cbc`)
- Current development focus: historical chip-opportunity calibration/backtesting
- Important rule: historical realised-outcome reports are diagnostic until look-ahead safety of archived pre-deadline inputs is proven.

## Current milestone

Latest merged work:

- PR #46
- Commit: `abe3e9f`
- Change: **Break realised chip backtests down by fixture shape**

The historical realised chip backtest now reports results separately by fixture shape so that blank-only, double-only, and mixed blank+double Gameweeks can be assessed independently.

## Why this was added

The aggregate realised-opportunity results after the previous refinements were:

- FH: Spearman `-0.461`
- BB: Spearman `+0.678`
- TC: Spearman `+0.279`

FH is still negative even after improving the realised outcome metric, so the next diagnostic question is whether several genuinely different Free Hit situations are being averaged into one misleading overall correlation.

## Relevant preceding work

### PR #33 — `f79316f`
**Backtest realised historical chip opportunities**

Added a first realised-outcome backtest using imported historical player/Gameweek data.

Initial realised metrics:

- TC: highest actual player score in the Gameweek
- FH: hindsight-optimal legal 15-man squad / XI / captain under FPL constraints
- BB: hindsight-optimal legal 15-man squad and bench-points ceiling

### PR #34 — `c02d609`
**Refine realised FH and TC backtest metrics**

Changed:

- FH to `fh_template_uplift_ceiling`: hindsight-optimal Free Hit score minus a legal template-squad baseline built from the most-owned historical players.
- TC to `tc_captainable_increment_ceiling`: realised captain ceiling restricted to the 20 most-owned players in the Gameweek.
- BB remained `bb_bench_ceiling`.

Latest aggregate results before PR #46:

### FH
- Cases: 30
- Metric: `fh_template_uplift_ceiling`
- Spearman signal/outcome: `-0.461`
- Mean realised outcome: `76.03`

### BB
- Cases: 36
- Metric: `bb_bench_ceiling`
- Spearman signal/outcome: `+0.678`
- Mean realised outcome: `38.31`

### TC
- Cases: 36
- Metric: `tc_captainable_increment_ceiling`
- Spearman signal/outcome: `+0.279`
- Mean realised outcome: `17.83`

## Immediate next step

On the Pi:

```bash
cd ~/busy-working-fpl-assistant
git pull
time python3 -m tools.backtest_historical_chip_outcomes
```

The most important new output is the **By fixture shape** section under FH.

Interpret the blank-only, double-only, and mixed blank+double groups separately. The main question is:

> Is FH genuinely badly modelled, or is the negative overall correlation caused by combining different classes of Free Hit opportunity that need separate feature models?

Do **not** blindly retune live FH thresholds until that diagnostic has been reviewed.

## Current working interpretation

- **BB** currently looks the strongest of the three historical fixture-pattern signals and should not be changed yet.
- **TC** has a positive but modest relationship; fixture structure alone is probably insufficient, but no retuning should happen until the current diagnostic pass is complete.
- **FH** is the immediate research target. If fixture shapes behave differently, split the FH model rather than continuing to force one score across all cases.

## Historical-data caveat

The realised outcome ceilings use actual FPL points.

Archived team-strength/FDR inputs have **not yet been proven to be exact pre-deadline snapshots**. Therefore the backtest is useful for diagnosis but is **not yet look-ahead-safe calibration**.

Do not use these reports alone to tune live production thresholds.

## Existing project context worth preserving

The app already includes:

- chip planning with HOLD recommendations;
- historical fixtures and analogue features;
- pre-deadline snapshot cadence at T-60, T-15, T-10 and T-5;
- read-only planner / Why? diagnostics;
- local Entry ID and refresh-token management;
- cached chip-plan warming;
- systemd service/timers on the Pi;
- CI/security work including CodeQL and dependency checks.

## Handoff rule

Whenever a meaningful development milestone is completed, update this file with:

1. latest merged PR/commit;
2. what changed;
3. latest important measurements/results;
4. unresolved question;
5. exact next command/action;
6. any caveat that a new conversation must not lose.

Prefer replacing stale detail rather than letting this become a chronological diary.

When starting a new ChatGPT conversation, the useful instruction is:

> Read `current_status.md` in the `DansJavaStuff/busy-working-fpl-assistant` repository first, then continue from the Immediate next step.
