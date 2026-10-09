## Current change — cautious advice (9 October 2026, evening)

- User completed free Richarlison → João Pedro transfer, then moved João Pedro into XI and Groß to captain. Refreshed HQ sees bank £0.1m / zero FT and still proposes three additional moves: Gabriel → Tarkowski, Scott → Schade, Dewsbury-Hall → Hinshelwood; hit 12, gross ranking gain 20.35, net 8.35. Hit accounting is correct; forecast sensitivity is the concern.
- User authorised a production change: six-GW form weight now capped at minutes/1080 (Hinshelwood 63 minutes → 5.83%, rather than 83.33%). Shared projection change applies to HQ and Chips.
- HQ paid plan must additionally clear the existing 3-point gate against its best tested no-hit squad with 12-GW minutes-capped form. Same purchases, legal XI/captain reoptimised without more CBC calls, hit deducted once. Failed check falls back to no-hit/free gate. No search for a lower paid alternative after failure.
- HQ and saved-report CLI show best owned-only HOLD lineup, captain/vice/bench, plus paid-check explanation. Weekly schema bumped to 5; chip cache context includes new model policy so prior results are invalidated. Research control follows new live policy; older bundles need fresh capture.
- This is a conservative response to small samples and sensitivity, not proof of improved accuracy. Need fresh Pi analysis on the post-transfer squad; do not promise HOLD or any particular captain. Forward snapshots/outcome validation remain the next evidence source.
- Previous result sections below are historical records of pre-change code, not current live policy. No FPL submission performed.

# Current Status

_Last updated: 2026-10-09_

Durable handoff for `DansJavaStuff/busy-working-fpl-assistant`. Read this first in a new conversation and replace stale details when milestones finish.

## Runtime and workflow

- Raspberry Pi; service `fpl-assistant`; CBC `/usr/bin/cbc`.
- Entry ID / refresh token are local configuration; never commit secrets.
- Existing features: chip HOLD recommendations, historical fixture analogues, read-only planner / Why? diagnostics, cache warmer, deadline snapshots T-60/T-15/T-10/T-5.
- User authorises pushes and merges once tests and required CI/security checks are green.
- Keep this file current as part of each meaningful milestone.

## Roadmap alignment (2026-10-04)

`ROADMAP.md` reviewed after PR #55. Core local dashboard, decision report and coordinated chip schedule are implemented; current focus is decision reliability and forward accuracy evidence. Historical reconstruction is deferred. Next session: refresh/review advice closer to GW6 deadline; leave collection running. No immediate repeat optimiser run or production model change is needed. Projection/outcome evaluation and broader model calibration remain open.

## Live Chips policy comparison ready (2026-10-09)

- Added explicit `--projection-policy chips` to the research command. Capture uses the same long-range regression and projection horizon arguments as the live Chips page. The saved policy is replayed unchanged across control, 12-GW and minutes-capped alternatives; control reproduction is checked before solving. Default weekly mode and live advice remain unchanged.
- Pi next command: `time nice -n 10 python3 -m tools.compare_form_sensitivity --include-wildcard --projection-policy chips`. Requires fresh capture after pulling because code signature changed. Replay automatically uses saved policy and rejects attempts to switch it. Full-pool results are now recorded below.
- Validation: 151 tests, compilation, undefined-name lint and dependency audit pass. Real CBC smoke exercises all three chip-policy variants and verifies control ranking-score parity with the live Wildcard analysis on identical synthetic inputs.
- This resolves the projection-settings mismatch for a fresh controlled run; it does not reproduce an old timestamp's exact advice, rerun full chip timing or account for future transfers/news. Highest-scoring tested normal plan remains distinct from HQ's threshold-selected plan.

## Latest live chip-policy result (2026-10-09)

- Pi capture 19:14:58 UTC under PR #60 (`346a5bc`) completed in 2m13.365s with successful control replay. Policy is explicitly chips/regression enabled. Control WC reproduces earlier displayed +21.5 ranking advantage (+21.5104) and roughly +25.1 five-week value vs best no-hit fixed squad (+25.0523), on this fresh capture. Full future timing curve was not rerun.
- Control selects three moves / 8-point hit (Scott → Schade, Richarlison → Kostoulas, Ajayi → Tarkowski). Both alternatives select one free Richarlison → João Pedro move; paid increments 1.6245 / 1.6097 fail the existing 3-point gate. All are hypothetical chip-policy normal plans, distinct from weekly-policy advice.
- WC advantage vs the selected free squad is +11.8667 (12-GW) / +12.7420 (minutes cap), but almost entirely GW6: +13.1424 / +12.9921 now and −1.2758 / −0.2501 over GW7–10 combined. This weakens the case for a lasting rebuild despite a positive headline. Future transfers and chip opportunity cost remain omitted.
- Both alternative WC squads are identical, nine changes, cost £99.4m. Hinshelwood and Semenyo drop out; Groß captain / Haaland vice persist in alternative normal plans. Detailed squad and evidence: [chip-policy result](docs/form_sensitivity.md#full-pool-live-chips-policy-pi-result--9-october-2026).
- No live weights, chip labels, reports or FPL team changed. Next practical step is decision review of the free move versus spending the Wildcard, with fresh team news and starting-role checks; broad historical reconstruction remains deferred. Do not interpret sensitivity results as calibrated forecasts or automatically retune thresholds.

## Controlled Wildcard review (2026-10-09)

- Pi GW6 advice now recommends three transfers with an 8-point hit; normal model gains are +8.71 / +12.73 / +15.33 for 1 / 2 / 3 moves. Chips flags WC as CANDIDATE (+25.1 five-week timing value); unrestricted selection changes 11 players and reports +21.5 ranking-score advantage over the best tested normal plan. These use different metrics/baselines.
- Saved chip report at 18:13:53 UTC includes Hinshelwood (50%, ep_next 0, PPG 16, roughly 63 minutes) and Semenyo (75%). Screenshots confirm ankle-injury flags. Hinshelwood's current PPG still receives 5/6 weight; only underlying-stat adjustments get minutes reliability. Later-GW injury penalties are absent. This is a reason to scrutinise recommendations, not proof that any replacement is correct.
- Added research-only `--include-wildcard` to `tools.compare_form_sensitivity`: same frozen pool/team across all three variants; normal gates unchanged; unrestricted WC and fixed-squad five-week evaluation against HOLD and normal plans; detailed squad/watch-player diagnostics. No live model/cache/report or FPL submission changes. See [form sensitivity](docs/form_sensitivity.md).
- Validation: 147 tests pass; undefined-name lint, compilation and dependency audit pass; a synthetic 18-player run exercised all 15 real CBC solves and fixed-squad evaluations without API calls. Full-pool Pi run subsequently completed in 2m9.797s.
- Next Pi step: `time nice -n 10 python3 -m tools.compare_form_sensitivity --include-wildcard` after pulling. Requires a fresh capture under the updated code signature and no active KEEP/INCLUDE constraints. Optional-mode full-pool result is now recorded below. Review before applying either the hit plan or Wildcard.

## Latest controlled comparison result (2026-10-09)

- Pi capture 18:51:15 UTC, PR #58 (`9d1bc7f`): control recommends the original three moves / 8-point hit (+15.3337 ranking gain). Both 12-GW alternatives choose one free Richarlison → João Pedro move (+6.5089 / +6.1625). Paid increments 2.6734 / 2.6862 narrowly fail the existing 3-point gate. Groß captain remains stable; vice changes to Haaland.
- Minutes cap reduces Hinshelwood's form weight to 63/1080 = 5.83%, GW6 projection to 1.7802 and five-week sum to 15.4102; he drops from the Wildcard. Semenyo is absent in all three WC squads. Availability inputs held fixed.
- Wildcard five-week fixed-squad gains versus selected normal: +33.0528 control / +36.2229 12-GW / +21.8958 capped. Against the highest-scoring tested normal plan, capped gain is +19.4375. All WC squads change ten players; exact selections vary. Positive model advantage is not calibrated accuracy or proof of ideal timing.
- Important boundary: research uses weekly `load_players()` defaults, without the separate `long_range_regression=True` used by the live Chips page. Its control does not reproduce the earlier chip report's +21.5 / +25.1 values or exact squad. Do not explain those cross-report differences purely as news or form-weighting effects. All three research variants are internally consistent.
- Full output interpretation and capped squad: [form sensitivity results](docs/form_sensitivity.md#full-pool-wildcard-pi-result--9-october-2026). Live models/reports/thresholds remain unchanged; no chip/transfer submitted. Next step is role/minutes review and comparison under consistent live chip projection policy before applying a rebuild.

## Latest milestone

- Early-season sensitivity investigation: research-only `tools.compare_form_sensitivity` captures one pool/squad for three fixed alternatives and offline replay. Exact control reproduction checked before solving; production weights unchanged.
- Initial supplied-player calculation: 12-GW weighting lowers Groß 8.668→7.519, Bogle 8.059→6.911, Haaland 6.999→6.791, Tarkowski 7.594→6.719, Mukiele 2.265→2.580. Groß remains captain among the three supplied candidates; Haaland overtakes Bogle for vice. Full-pool Pi result now confirms the same free Mukiele→Tarkowski transfer and Groß captain under all three variants; vice changes Bogle→Haaland. Net gain +7.0136 / +5.0498 / +4.9785.
- Prior merged code: PR #54, `6d3c8f2`; 143 tests, compilation, undefined-name lint, dependency audit, CBC smoke check and CI/security passed.
- Pi comparison completed in 1m37.589s (user 1m33.819s, system 1.387s). Control three-transfer plan adds only +2.8502 vs best free, 0.1498 below the 3-point gate; reduced-form best paid increments are +0.2750 / +0.0109.
- No production weighting/threshold change: stable transfer/captain in this one capture is not proof of accuracy. See `docs/form_sensitivity.md` for results and the separate-capture three-transfer discrepancy.
- Prior merged code: PR #53, `748fdaf` — live planner refresh/freshness and transfer hit display fixes. Pi supplied output confirms display/selection gates: one free Mukiele→Tarkowski transfer (+7.014); paid options add only +1.812/+2.068 vs best free plan and fail the 3-point gate.
- GW6 chips: BB +5.5 / best later GW9 +7.8; TC +8.7 / later GW16 +7.3; WC +12.7 / later GW10 +20.0; FH +16.7 / later GW12 +8.2. All HOLD, matching normal-slate/ranking gates. These remain provisional model values.
- Supplied current captain/vice model is Groß/Bogle; Richarlison unavailable and benched. User emphasises ongoing international duty and later team news: review mechanics now, defer final squad decisions until closer to deadline.
- Pi timer enabled/active; GW6 baseline saved and all later checkpoints pending. Stored deadline 2026-10-10 10:00 UTC (11:00 BST).

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

Pause full historical reconstruction. The user agreed to useful improvements before the restart; prioritise current-season collection reliability and practical decision support.

Current snapshot reliability change: timing now uses completed collection and the fresh bootstrap deadline; post-deadline completions are discarded. `python3 -m tools.snapshot_health` reads the recorded heartbeat and latest stored Gameweek, recomputes checkpoint timing and checks required payload presence without writes or API calls. It omits team details/error text and separates entries. This is not proof of timer enablement or forecast accuracy.

Full-pool sensitivity comparison is complete. Leave live weighting unchanged and use later pre-deadline snapshots plus realised outcomes to judge accuracy. No immediate repeat optimiser run is needed. The saved input bundle can be replayed if further analysis is required; avoid mixing separate captures when attributing changes to weights.

Snapshot collection is verified as scheduled; leave it running. Refresh live planner advice later in the week as availability/team news settle. This is not a recommendation to apply the early GW6 plan.

After 4–5 complete Gameweeks, compare checkpoint changes and realised outcomes to decide whether later checkpoints add value. No live chip thresholds change here.

Historical deadline catalogue and fixture reconstruction remain deferred. The historical results stay diagnostic; a chronological split alone cannot repair revised inputs.

## Caveats that must survive handoff

Archived fixtures and rating fields have confirmed retrospective revisions; they are not deadline snapshots. FH selection uses prior-GW ownership and form proxies; season-level LOSO is not chronological walk-forward validation. BB and TC still use hindsight ceilings. These are research diagnostics, not sufficient evidence for retuning live thresholds.

Top-week regret compares only the observed blank weeks in a season, without modelling chip inventory, availability or a real manager's squad and transfer options. Five seasons / 22 cases give limited stability evidence. Gate thresholds are research heuristics, not statistical significance claims.
