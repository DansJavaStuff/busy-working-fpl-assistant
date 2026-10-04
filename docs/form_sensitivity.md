# Early-season form sensitivity

This is a research comparison, not a new production model. Live projections still use `min(completed_gameweeks / 6, 1)` as the current-season PPG weight. No chip thresholds, captain weights or transfer gates change.

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

- `control_6gw`: unchanged six-completed-GW weighting.
- `form_12gw`: `min(completed_gameweeks / 12, 1)`.
- `form_12gw_minutes_cap`: cap the 12-GW weight further at `minutes / 1080`, equivalent to twelve full matches of minutes. This is an exposure proxy, not a count of actual appearances.

The projection function accepts an explicit research override; default callers retain the original rule. Players now preserve their original projection inputs and availability factor for replay. The control must reproduce all five captured weekly projections to within 1e-9 before any solver comparisons proceed. Bundles must match the projection/context/transfer/research code signature; a model-code change requires a new capture.

The output reports recommended transfers/hits/gains, captain/vice, owned captain rankings and stability across variants. It reproduces HQ's existing free/paid transfer gates, including the 3-point additional net-gain gate for paid plans. Gains are compared with HOLD *within each variant*; do not interpret a lower absolute score under stronger shrinkage as worse performance.

The captured bundle path is printed before solving. To replay later without API calls or changes to that bundle:

```bash
python3 -m tools.compare_form_sensitivity --input data/runtime/form_sensitivity/PASTE_CAPTURE_FILENAME.json
```

To capture now and defer solving, use `--capture-only`. A failed solve leaves its saved input bundle available for replay. On the Pi, CBC remains `/usr/bin/cbc`. This is 12 solves over one pool; the first full-pool Pi run took 1m37.589s, with future duration dependent on inputs and system load.

## Interpretation and limits

- FPL `ep_next`, fixtures, priors, availability, captain multipliers and transfer gates remain fixed. `ep_next` may itself contain form information, so these variants do not remove all early-season form influence.
- Availability and team news can change after capture, especially during international duty. These are provisional research rankings, not an instruction to apply today's plan. Refresh live advice closer to the deadline.
- Three fixed alternatives are a sensitivity check, not tuning against a preferred player. Stability does not prove accuracy; instability identifies a decision to scrutinise.
- The tool compares transfer/captain advice, not chip values or future news. It is not an evaluation of realised points.
- An infeasible HOLD baseline, including an incoming INCLUDE constraint, prevents a meaningful comparison and stops the run. A larger transfer-count search is out of scope.
- Next evidence: refreshed pre-deadline advice, chronological live snapshots and realised outcomes. Do not promote an alternative solely because it makes a familiar player captain or changes this week's transfer.
