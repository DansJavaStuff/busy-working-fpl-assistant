# Current Status

_Last updated: 2026-10-04_

Durable handoff for `DansJavaStuff/busy-working-fpl-assistant`. Read this first in a new conversation and replace stale details when milestones finish.

## Runtime and workflow

- Raspberry Pi; service `fpl-assistant`; CBC `/usr/bin/cbc`.
- Entry ID / refresh token are local configuration; never commit secrets.
- Existing features: chip HOLD recommendations, historical fixture analogues, read-only planner / Why? diagnostics, cache warmer, deadline snapshots T-60/T-15/T-10/T-5.
- User authorises pushes and merges once tests and required CI/security checks are green.
- Keep this file current as part of each meaningful milestone.

## Latest milestone

- Previous merged code: PR #48, `66ae9f7` — blank-only FH ranking stability benchmark; results recorded by PR #49, `12d8775`.
- Latest merged code: PR #50, `13db55e` — deadline-input source/code audit, pinned evidence and read-only Pi provenance helper.
- Pi provenance check completed on 2026-10-04: import SHA matches the audited source head, and both target fixture rows match the final rearrangements.
- Audit verification: 112 unit tests, compilation, undefined-name lint, runtime dependency audit and GitHub CI/CodeQL all passed before merge.
- The user has now run the benchmark on the Pi; findings below are from that supplied output.
- No live FH thresholds, BB metrics or TC metrics change in this milestone.

## Latest supplied historical results

Five seasons: 2021-22 to 2025-26. The latest Pi run took 12m45.1s.

- FH now uses pre-deadline-proxy-selected template and Free Hit squads scored afterwards, allowing negative uplift. It is no longer just the earlier hindsight ceiling.
- FH fixture signal: overall +0.270; blank-only +0.651 (22 cases); mixed blank+double -0.359 (8 cases).
- Blank-only regressed-form LOSO comparison: fixture +0.534, projection +0.342, equal-rank blend +0.562. The stability verdict is HOLD / fixture-only: the pooled improvement is not robust enough to promote the blend.
- Optimiser selection magnifies projection errors: player correlation 0.569 across active players, 0.212 in FH XIs. 8+ projected points averaged 9.01 projected vs 5.50 actual.
- Hybrid player calibration remains HOLD: ranking 0.385 improved, but MAE 15.33 exceeds the simpler position-regression benchmark 13.82.
- BB remains a hindsight bench ceiling: +0.678 overall; mixed +0.945; doubles +0.624.
- TC remains a top-20-owned captainable ceiling: +0.279 overall; mixed +0.443; doubles +0.283.

## Blank-only ranking stability result

- Blend improves within-season correlation in 2/5 seasons: +0.084 (2021-22), -0.200 (2022-23), 0 (2023-24), +0.134 (2024-25), 0 (2025-26).
- Removing 2023-24 reverses pooled advantage to -0.018; removing 2024-25 gives -0.013. Other season-deletion deltas: +0.034, +0.077, +0.042.
- The majority-improvement and no-negative-deletion gates fail; the other three gates pass. Keep the fixed gate rather than relaxing it after seeing results.
- Equal-season mean top-week regret improves from 8.8 points (fixture) to 2.6 (blend).
- 2022-23: blend chooses GW8 (+23 actual uplift) instead of GW28 (+6), despite poorer full-season rank correlation.
- 2024-25: blend chooses GW34 (+38), while fixture ties GW29/GW34 (tie-averaged +24).
- Other seasons have the same first choices. The 6.2-point mean regret improvement comes from those two seasons; promising decision evidence, not established generalisation.
- These choice outcomes use regressed-form squads, whereas the headline FH archetype metrics use the current proxy. Do not mix their outcome values.

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

## Deadline-input audit (2026-10-04)

Source/code audit and targeted Pi provenance verification are complete; see `docs/historical_input_audit.md` and its pinned JSON evidence. This is not a byte-for-byte check of every imported row.

- Confirmed retrospective fixture contamination: Bournemouth–Luton (2023-24 fixture 162) moves from scheduled GW17 to final GW28 after the GW17 deadline; final schedule produces 9 rather than 10 GW17 fixtures.
- Confirmed FDR revisions: 168/380 2023-24 fixtures differ between December/final files, including 72 assigned to completed GW1–16.
- All 20 2023-24 teams change strength-related values. Application top-six premium clubs change, affecting even FH fixture-only signal.
- Everton–Liverpool GW15 was postponed BEFORE the 2024-25 deadline, but the latest Git file beforehand was stale. Pre-deadline Git timestamps alone cannot establish exact known availability.
- 2025-26 archive has sparse updates; earlier-GW player filtering is only a partial safeguard. Actual capture/correction timing remains unknown. No repaired-input correlations or live threshold changes have been computed.
- Backtest caution now explicitly labels retrospective fixture inputs and links to the audit. Provenance helper reads SQLite in read-only mode without migrations/network/credentials.

## Pi provenance findings (2026-10-04)

- All five historical import records list source SHA `9779cdbc0c07f6c900c2d0c181ddf6bb9c800f88`, exactly the source head inspected in the audit, covering fixtures, teams and merged player GWs.
- Each historical season has 38 Gameweeks / 380 fixtures, but zero deadline timestamps: **190/190 historical deadlines are missing**.
- Stored 2023-24 fixture 162 is GW28 / 2024-03-13 19:30 UTC / FDR 2–2; stored 2024-25 fixture 144 is GW24 / 2025-02-12 19:30 UTC / FDR 5–3. Both match the final-source rows in the audit.
- Fixture source_updated_at timestamps are from 25 September 2026, while import log timestamps are from 26 September. These are import metadata, not historical collection times; the mismatch reinforces that logs are not per-row lineage.
- The separate current-season 2026-27 row has one recorded Gameweek/deadline and no historical fixtures. This report does not diagnose the live API or snapshot timers.
- Provenance command completed in 0.519s. No repeat audit command or optimiser run is needed for these unchanged inputs.

## Immediate next step

Proposed next implementation: create an evidence-backed historical deadline catalogue in UTC, recording source references and leaving unresolved deadlines missing rather than inferring them from final fixture kickoffs. The current 190 missing deadlines prevent reliable before/after comparisons.

Then build immutable dated decision snapshots / evidenced fixture amendments, separate from final outcomes, with explicit verified/stale/unknown coverage. Recreate candidate weeks from deadline-known schedules; only then test expanding chronological validation. A chronological training split cannot repair hindsight fixture/FDR leakage by itself. Keep fixture-only as provisional research baseline, blend HOLD and mixed FH uncalibrated. This reconstruction has not yet been implemented.

## Caveats that must survive handoff

Archived fixtures and rating fields have confirmed retrospective revisions; they are not deadline snapshots. FH selection uses prior-GW ownership and form proxies; season-level LOSO is not chronological walk-forward validation. BB and TC still use hindsight ceilings. These are research diagnostics, not sufficient evidence for retuning live thresholds.

Top-week regret compares only the observed blank weeks in a season, without modelling chip inventory, availability or a real manager's squad and transfer options. Five seasons / 22 cases give limited stability evidence. Gate thresholds are research heuristics, not statistical significance claims.
