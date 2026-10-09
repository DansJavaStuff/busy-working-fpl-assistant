# Early-season form sensitivity

The comparison remains research-only. As of 9 October's cautious-advice change,
live projections use `min(completed_gameweeks / 6, minutes / 1080, 1)`.
HQ additionally checks paid plans with the 12-GW minutes-capped variant before
recommending them. The numeric gates, captain weights and objective remain unchanged.
Earlier results below record the previous uncapped production model; they are not
predictions for the new code or the squad after Richarlison → João Pedro.


## Initial supplied GW6 evidence

Recomputing the supplied five player records with their other inputs held fixed gives:

| Player | Current 6-GW rule | 12-GW rule | 12-GW rule with minutes cap |
|---|---:|---:|---:|
| Groß | 8.668 | 7.519 | 7.519 |
| Bogle | 8.059 | 6.911 | 6.694 |
| Haaland | 6.999 | 6.791 | 6.791 |
| Tarkowski | 7.594 | 6.719 | 6.719 |
| Mukiele | 2.265 | 2.580 | 2.643 |

The current-season weight goes from 5/6 to 5/12 in the second column of alternatives. Captain weighting still favours Groß under these alternatives. Haaland overtakes Bogle on captain score, changing the vice ranking among these three players. These are projections, not observed outcomes; the initial calculation is limited to the supplied players. It cannot establish the full optimiser's transfer choices or their accuracy.

## Full-pool Pi result — 4 October 2026

Frozen inputs captured at 19:33:59 UTC using PR #54 (`6d3c8f2`). This uses the same pool/squad across all variants, with successful control replay.

| Weighting | Recommended transfer | Hit | Net model gain vs own HOLD | Captain | Vice |
|---|---|---:|---:|---|---|
| Current 6-GW rule | Mukiele → Tarkowski | 0 | +7.0136 | Groß | Bogle |
| 12-GW rule | Mukiele → Tarkowski | 0 | +5.0498 | Groß | Haaland |
| 12-GW with minutes cap | Mukiele → Tarkowski | 0 | +4.9785 | Groß | Haaland |

Transfer and captain choices survive all three alternatives; vice choice does not. The estimated transfer gain is roughly 28–29% smaller with reduced form weighting. This is stability within one frozen-input comparison, not calibration or evidence of realised accuracy.

Paid plans still fail HQ's additional-net-gain threshold of 3 over the best no-hit plan. Under control, the three-transfer plan adds 9.8638 − 7.0136 = 2.8502, only 0.1498 below the gate. Under the 12-GW rule, the best paid plan adds 0.2750; under the minutes cap, 0.0109. The control result is close to the gate, so do not describe all paid options as decisively poor.

The control three-transfer gain (+9.8638) differs from the earlier separately captured weekly report (+9.0814). The one-transfer choice/gain and captain projection match. Because those runs used separate captures, this difference does not identify a weighting effect or establish its cause; no same-input cross-command reconciliation was performed.

Pi runtime: **1m37.589s** elapsed, 1m33.819s user, 1.387s system, using `nice -n 10`. This is one observation, not a guaranteed future duration. The saved input bundle allows replay without recapturing news/availability.

Decision: retain live weights and thresholds. The vice ranking deserves scrutiny, but this single week does not justify promoting a new model. No transfer/captain changes were submitted. Refresh provisional live advice later in the week and evaluate future decision snapshots against realised outcomes.

## Full-pool command on the Pi

```bash
time python3 -m tools.compare_form_sensitivity
```

The command fetches fresh official bootstrap/fixtures, loads one projection pool and live squad, then saves a private, uniquely named input bundle under ignored `data/runtime/form_sensitivity/`. Capture uses existing third-party depth-chart and historical-prior mechanisms; the responses are sequential, not an atomic API snapshot. Same-GW KEEP/INCLUDE constraints are copied from the saved weekly report if present. It never calls transfer/team submission endpoints or writes the weekly recommendation/approval/report.

Three variants run on that same input bundle, each solving 0–3 transfers:

- `control_6gw`: current live six-completed-GW weighting, now capped at `minutes / 1080`.
- `form_12gw`: `min(completed_gameweeks / 12, 1)`.
- `form_12gw_minutes_cap`: cap the 12-GW weight further at `minutes / 1080`, equivalent to twelve full matches of minutes. This is an exposure proxy, not a count of actual appearances.

The projection function accepts an explicit research override; default callers use the live minutes-capped six-GW rule. Players now preserve their original projection inputs and availability factor for replay. The control must reproduce all five captured weekly projections to within 1e-9 before any solver comparisons proceed. Bundles must match the projection/context/transfer/research code signature; a model-code change requires a new capture.

The output reports recommended transfers/hits/gains, captain/vice, owned captain rankings and stability across variants. It uses the original free/paid score gates, including the 3-point additional net-gain gate for paid plans. It does not apply HQ's new additional paid-plan sensitivity gate: projection control reproduction does not guarantee the same final recommendation. The output explicitly reports `live_paid_sensitivity_gate_applied: false`. Gains are compared with HOLD *within each variant*; do not interpret a lower absolute score under stronger shrinkage as worse performance.

The captured bundle path is printed before solving. To replay later without API calls or changes to that bundle:

```bash
python3 -m tools.compare_form_sensitivity --input data/runtime/form_sensitivity/PASTE_CAPTURE_FILENAME.json
```

To capture now and defer solving, use `--capture-only`. A failed solve leaves its saved input bundle available for replay. On the Pi, CBC remains `/usr/bin/cbc`. This is 12 solves over one pool; the first full-pool Pi run took 1m37.589s, with future duration dependent on inputs and system load.

## Interpretation and limits

- FPL `ep_next`, fixtures, priors, availability, captain multipliers and transfer gates remain fixed. `ep_next` may itself contain form information, so these variants do not remove all early-season form influence.
- Availability and team news can change after capture, especially during international duty. These are provisional research rankings, not an instruction to apply today's plan. Refresh live advice closer to the deadline.
- Three fixed alternatives are a sensitivity check, not tuning against a preferred player. Stability does not prove accuracy; instability identifies a decision to scrutinise.
- The default tool compares transfer/captain advice. Optional Wildcard mode adds the existing unrestricted selection and fixed-squad evaluation described below; it does not evaluate realised points or forecast future news.
- An infeasible HOLD baseline, including an incoming INCLUDE constraint, prevents a meaningful comparison and stops the run. A larger transfer-count search is out of scope.
- Next evidence: refreshed pre-deadline advice, chronological live snapshots and realised outcomes. Do not promote an alternative solely because it makes a familiar player captain or changes this week's transfer.

## Controlled Wildcard comparison — 9 October 2026

The supplied GW6 Wildcard report changed 11 players and included Hinshelwood (50% availability, 16 PPG with approximately 63 current-season minutes) and Semenyo (75%). Website screenshots confirmed both ankle-injury flags. Hinshelwood retained an 83.3% current-season PPG weight despite that tiny sample; the separate minutes reliability only protects underlying statistics. The optional comparison now exposes this behaviour across the same three weighting alternatives. It does not alter live projections or infer an injury recovery date.

```bash
time nice -n 10 python3 -m tools.compare_form_sensitivity --include-wildcard
```

Use a new capture after updating code: the signature now also includes `chip_planner.py`. Earlier captures remain untouched but cannot replay under this version. `--input PATH --include-wildcard` replays a compatible capture without API calls. Default mode remains 12 normal solves; optional mode adds one unrestricted Wildcard solve per variant (15 CBC solves in total), plus inexpensive fixed-squad lineup enumeration. Runtime on the Pi has not yet been measured for this mode.

For a fair unrestricted comparison, optional mode stops before solving if the saved weekly report has active KEEP/INCLUDE constraints. Clear those constraints in the app, refresh the weekly report, and capture again; the research command never clears them itself.

Each variant reports:

- The normal 0–3-transfer options and HQ-selected plan, with existing gates unchanged.
- An unrestricted legal Wildcard using total official selling values plus bank as its budget, with current player purchase prices as in the existing chip solver.
- Wildcard ranking gains against HOLD, the HQ-selected normal plan and the highest-scoring tested normal plan, explicitly distinguishing these baselines.
- Five-week fixed-squad projections for HOLD, best no-hit plan, selected normal plan, highest-scoring normal plan and Wildcard. Each initial squad is held fixed, its legal XI/captain is reselected each week using existing captain ranking, projected points include the captain's extra unweighted projection, and the initial transfer hit is deducted once from the total. These are modelled projections, not observed or calibrated returns.
- Every Wildcard player's price, current availability/status, raw minutes/PPG, form weight, starting-probability assumption, weekly projections and fixtures; Hinshelwood/Semenyo are shown separately even if no longer selected. Private entry IDs, tokens and full captured team state are omitted.

The Wildcard squad still uses the existing selection objective: current XI plus position-weighted captain score plus 15% of the squad's five-week projection. The five-week assessment is a separate evaluation of those selected squads, not an optimisation over all weekly transfers, future news, autosubs or prices. It does not create a chip recommendation, update the live Chips cache/report, activate a chip or submit transfers. Current injury penalties affect the first GW only, exactly as in control; later uncertainty remains a limitation rather than an invented recovery forecast. The comparison does not reproduce the full future chip-timing curve.

Assess whether the Wildcard and paid normal plans survive stronger sample protection before interpreting the earlier +25.1 timing value or +21.5 selection-score advantage. Those earlier figures use different metrics/baselines and must not be added or compared directly with one another. No live weight change is justified solely by this one sensitivity run.

## Full-pool Wildcard Pi result — 9 October 2026

Frozen inputs captured at **18:51:15 UTC** under PR #58 (`9d1bc7f`), with successful control replay. Runtime **2m9.797s** elapsed, 2m6.164s user, 1.551s system. No FPL changes submitted; live weights remain unchanged.

| Variant | HQ-selected normal plan | Hit | Normal ranking gain vs own HOLD | WC ranking gain vs selected normal | WC fixed-squad five-week gain vs selected normal | WC five-week gain vs highest-scoring tested normal |
|---|---|---:|---:|---:|---:|---:|
| Control 6-GW | Scott → Schade; Dewsbury-Hall → Hinshelwood; Mukiele → Tarkowski | 8 | +15.3337 | +28.9234 | +33.0528 | +33.0528 |
| 12-GW | Richarlison → João Pedro | 0 | +6.5089 | +22.8215 | +36.2229 | +34.5941 |
| 12-GW, minutes cap | Richarlison → João Pedro | 0 | +6.1625 | +20.8391 | +21.8958 | +19.4375 |

The paid normal plan fails HQ's 3-point additional ranking-gain gate under both alternatives: its incremental gains above the best free plan are 2.6734 and 2.6862. These are close to the threshold, not proof that paid transfers are always poor. Normal transfer choice is unstable; Groß remains captain in all three variants and vice changes from Schade to Haaland.

Hinshelwood's current PPG weight falls from 83.33% to 41.67% to 5.83%, using his captured 63 minutes. His GW6 projection falls from 5.9747 to 3.7196 to 1.7802, and his five-week sum from 51.7187 to 32.1980 to 15.4102. He appears in control and 12-GW Wildcards but drops out with the minutes cap. Semenyo is absent from all three Wildcard squads; his 75% flag remains unchanged. The flags are held fixed, so these changes cannot be attributed to new injury news within the comparison.

All three Wildcards change ten players, but the exact squad varies. Ten players are common: Raya, Tzolakis, Bogle, Gvardiol, Tarkowski, Belloumi, Groß, Schade, Haaland and João Pedro. The minutes-capped squad costs £99.2m within a £99.4m selling-value-plus-bank budget. Its GW6 XI is Raya; Bogle, De Cuyper, Gvardiol, Tarkowski; Belloumi, Groß, Schade; Haaland, João Pedro, Kostoulas. Remaining squad: Tzolakis, Gabriel, Bruno G., Tavernier. These are research selections, not submitted moves or verified starting lineups.

**Comparison boundary:** research capture uses `load_players()` with the normal weekly planner's default `long_range_regression=False`. The live Chips page loads with `long_range_regression=True`; that adds a separate regression towards priors for fallback/future projections. Therefore the research control is a weekly-model control, not a reproduction of the earlier Chips-page +21.5 advantage, +25.1 timing value or exact 11-change squad. All variants within this run share the same policy, inputs and baselines. The differences across those variants remain meaningful, but absolute research numbers must not be presented as refreshed live chip-timing values.

Interpretation: the eight-point plan is sensitive to early-form weighting and Hinshelwood's tiny sample. A positive hypothetical Wildcard advantage survives both alternatives, including roughly +19.4 five-week projected points over the highest-scoring tested normal plan under the cap. That supports further review of a rebuild, not proof of accuracy or optimal Wildcard timing. The normal squads are held fixed after their initial moves; future free transfers, chip opportunity cost, recovery uncertainty and starting-role uncertainty are not modelled. Next review: minutes/starting roles of the capped Wildcard squad, then a consistent comparison under the live chip projection policy before activating anything. Do not promote new live weights from this single result.

## Live Chips projection-policy comparison

To resolve the projection-policy boundary found in the first Wildcard run:

```bash
time nice -n 10 python3 -m tools.compare_form_sensitivity --include-wildcard --projection-policy chips
```

Capture uses exactly the live Chips `load_players` arguments: `long_range_regression=True` and a projection end derived from the chip-half boundary plus the five-week Wildcard horizon, capped at season end. The frozen bundle records `projection_policy=chips`; output also states that policy and the regression flag. Each replayed variant passes `long_range_regression=True` through the same production projection function. The existing long-range regression's sample/horizon factors are retained; only the current-season PPG blend changes across variants. The control must reproduce the first five captured weekly projections before solving. This regression applies when the production function does not use a positive current-GW `ep_next`, including fallback current-GW estimates.

The default remains `--projection-policy weekly`, with the normal planner's unchanged projection settings. A compatible offline replay automatically uses its saved policy:

```bash
python3 -m tools.compare_form_sensitivity --input data/runtime/form_sensitivity/PASTE_CAPTURE_FILENAME.json --include-wildcard
```

An explicit `--projection-policy` on replay must match the bundle; changing that argument cannot relabel or convert an earlier capture. These code changes alter the model signature, so capture fresh inputs after pulling; prior frozen bundles remain untouched.

The chip-policy comparison uses the same normal/HOLD/Wildcard metrics and baselines as the first research comparison. It reuses live projection settings and the unrestricted squad objective, but does not rerun the full future chip-timing curve or change strategic thresholds, injury assumptions, live cache/report or FPL team. The normal plan still applies HQ's existing free/paid gates; the highest-scoring tested normal baseline is reported separately, matching the baseline used for the live unrestricted Wildcard selection-score comparison. Compare variants within this newly frozen run. Do not attribute differences from older captures entirely to the policy change; those captures also have different timestamps and may have different news/input values.

Full-pool Pi chip-policy results remain pending. The previous weekly-policy run took 2m9.797s; chip policy still uses 15 CBC solves and fixed-squad evaluations, but no new runtime guarantee is made.

## Full-pool live Chips-policy Pi result — 9 October 2026

Capture **19:14:58 UTC**, PR #60 (`346a5bc`), `projection_policy=chips`, `long_range_regression=true`. Control replay passed. Runtime **2m13.365s** elapsed, 2m9.029s user, 1.622s system. This run retains live chip projection policy across all three alternatives; no live advice or FPL team was changed.

| Variant | Selected normal plan | Hit | Normal ranking gain vs HOLD | WC changes | WC five-week gain vs best no-hit plan | WC five-week gain vs highest-ranking tested normal |
|---|---|---:|---:|---:|---:|---:|
| Control 6-GW | Scott → Schade; Richarlison → Kostoulas; Ajayi → Tarkowski | 8 | +11.3211 | 11 | +25.0523 | +23.4362 |
| 12-GW | Richarlison → João Pedro | 0 | +6.3130 | 9 | +11.8667 | +13.8506 |
| 12-GW, minutes cap | Richarlison → João Pedro | 0 | +6.1085 | 9 | +12.7420 | +14.1844 |

The control's unrestricted WC ranking advantage is +21.5104, and its five-week advantage against the best no-hit fixed squad is +25.0523, consistent at display precision with the earlier live chip report's +21.5 and +25.1. This is a fresh capture, not proof of identical raw inputs or a rerun of all future timing windows. The control normal transfer pairs differ from the weekly-policy result; do not conflate weekly advice with chip-policy hypothetical normal plans.

Under both alternatives, the best paid ranking plan adds only +1.6245 / +1.6097 over the best no-hit plan, below HQ's additional-gain gate of 3. Their five-week projected totals are also lower than the selected free-transfer squad: 307.1056 vs 309.0895 for 12-GW; 306.2022 vs 307.6446 with the cap. Highest ranking score is not the same as highest five-week projection.

**The remaining Wildcard gain is concentrated in GW6:**

| Variant | WC vs best no-hit squad, GW6 | WC vs same squad, GW7–10 combined | Five-week total advantage |
|---|---:|---:|---:|
| Control | +17.5780 | +7.4744 | +25.0523 |
| 12-GW | +13.1424 | −1.2758 | +11.8667 |
| 12-GW, minutes cap | +12.9921 | −0.2501 | +12.7420 |

Weekly components use rounded report values and may differ from the unrounded total by 0.0001. Under stronger form protection, the model does not show a continuing GW7–10 benefit from the rebuilt fixed squad over the free-transfer fixed squad. Spending the Wildcard therefore needs justification beyond a positive five-week headline, particularly because future free transfers and the opportunity cost of using the chip remain omitted. This is model evidence, not proof that holding the chip is optimal.

Both alternative Wildcards select the identical 15 players and GW6 starters: Raya; Bogle, De Cuyper, Gvardiol, Tarkowski; Belloumi, Groß (captain), Schade; Haaland, João Pedro, Kostoulas. Remaining squad: Kelleher, Gabriel, Bruno G., Stach. Cost £99.4m within a £99.4m selling-value-plus-bank budget, nine changes from the captured owned squad. Hinshelwood and Semenyo are absent; current control retains both on its bench. Outfield expected starting probability remains an assumption of 1.0, not verified team news; Bruno G. has only 123 captured minutes despite a 100% availability flag.

Hinshelwood's chip-policy GW6 projection is 3.4877 / 2.5481 / 1.7400 across the variants, with the cap retaining the same 50% injury flag. Groß remains captain in all variants; alternative vice is Haaland rather than Schade.

Decision evidence: the large-hit recommendation is sensitive to form weighting, and the rebuilt squad's conservative five-week gain is primarily a current-GW effect. A free Richarlison → João Pedro move is a consistent research alternative across reduced-form settings; it is not submitted advice or a production-model promotion. Review current team news and the cost of spending the Wildcard before committing. Do not launch another broad historical reconstruction or alter live weights solely to match these preferences. Live models, chip labels and thresholds remain unchanged.
